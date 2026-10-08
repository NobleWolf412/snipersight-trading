"""Two requests must not mutate the engine while an earlier worker is running."""
import asyncio
import threading
import ast
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services.scanner_service import ScannerService


class ControlledEngine:
    def __init__(self):
        self.config=SimpleNamespace()
        self.started=threading.Event()
        self.release=threading.Event()
        self.finished=threading.Event()
        self.observed=[]
        self.applied=[]

    def apply_mode(self,mode):
        self.mode=mode.name
        self.applied.append(mode.name)

    def scan(self,symbols,progress=lambda *args:None):
        before=(self.mode,self.config.leverage,self.exchange_adapter.name)
        if symbols==['FIRST']:
            self.started.set()
            assert self.release.wait(5), 'fixture worker was not released'
        after=(self.mode,self.config.leverage,self.exchange_adapter.name)
        self.observed.append((symbols[0],before,after))
        progress(1,1,symbols[0])
        if symbols==['FIRST']:
            self.finished.set()
        return [],dict(total_rejected=0,by_reason={},details={})

    def scan_with_heartbeat(self,symbols):
        return self.scan(symbols,lambda *args:None)


def service_for(engine,**kwargs):
    service=ScannerService(engine,{'first':lambda:SimpleNamespace(name='first'),
                                  'second':lambda:SimpleNamespace(name='second')},**kwargs)
    service._transform_signals=lambda *args:([],[])
    return service


def test_overlapping_jobs_keep_mode_leverage_and_exchange():
    async def scenario():
        engine=ControlledEngine();service=service_for(engine)
        first=await service.create_scan(target_symbol='FIRST',exchange='first',sniper_mode='overwatch',leverage=2)
        try:
            assert await asyncio.to_thread(engine.started.wait,2)
            second=await service.create_scan(target_symbol='SECOND',exchange='second',sniper_mode='strike',leverage=7)
            await asyncio.sleep(.1)
        finally:
            engine.release.set()
        await asyncio.gather(first.task,second.task)
        assert first.status==second.status=='completed'
        for _,before,after in engine.observed:
            assert before==after
        assert first.metadata['mode']=='overwatch' and second.metadata['mode']=='strike'
    asyncio.run(scenario())


def test_cancelled_request_retains_worker_exclusion_until_worker_finishes():
    async def scenario():
        engine=ControlledEngine();service=service_for(engine)
        first=await service.create_scan(target_symbol='FIRST',exchange='first',sniper_mode='overwatch',leverage=2)
        try:
            assert await asyncio.to_thread(engine.started.wait,2)
            assert service.cancel_job(first.run_id)
            await asyncio.gather(first.task,return_exceptions=True)
            second=await service.create_scan(target_symbol='SECOND',exchange='second',sniper_mode='strike',leverage=7)
            await asyncio.sleep(.1)
        finally:
            engine.release.set()
        await second.task
        assert await asyncio.to_thread(engine.finished.wait,2)
        for _,before,after in engine.observed:
            assert before==after
        assert first.status=='cancelled' and first.progress==0 and not first.metadata
        assert second.status=='completed'
    asyncio.run(scenario())


def test_queued_cancellation_never_reconfigures_engine():
    async def scenario():
        engine=ControlledEngine();lock=threading.Lock();service=service_for(engine,orchestrator_lock=lock)
        lock.acquire()
        try:
            job=await service.create_scan(target_symbol='SECOND',exchange='second')
            await asyncio.sleep(.05)
            assert job.status=='queued' and not engine.applied
            assert service.cancel_job(job.run_id)
            await asyncio.gather(job.task,return_exceptions=True)
        finally:
            lock.release()
        # The cancelled worker must release the lock without constructing an adapter.
        sentinel=await service.create_scan(target_symbol='SECOND',exchange='second')
        await sentinel.task
        assert engine.applied==['stealth'] and job.status=='cancelled'
    asyncio.run(scenario())


def test_failure_releases_engine_and_log_recipient():
    async def scenario():
        engine=ControlledEngine();recipients=[]
        service=service_for(engine,log_handler=SimpleNamespace(set_current_job=recipients.append))
        failed=await service.create_scan(target_symbol='SECOND',exchange='unavailable')
        await failed.task
        valid=await service.create_scan(target_symbol='SECOND',exchange='second')
        await valid.task
        assert failed.status=='failed' and 'Unsupported exchange' in failed.error
        assert valid.status=='completed' and recipients==[failed,None,valid,None]
    asyncio.run(scenario())


def test_cancelled_worker_does_not_clear_next_jobs_logs():
    async def scenario():
        engine=ControlledEngine();recipients=[]
        service=service_for(engine,log_handler=SimpleNamespace(set_current_job=recipients.append))
        first=await service.create_scan(target_symbol='FIRST',exchange='first')
        try:
            assert await asyncio.to_thread(engine.started.wait,2)
            service.cancel_job(first.run_id)
            second=await service.create_scan(target_symbol='SECOND',exchange='second')
            await asyncio.sleep(.05)
            assert recipients==[first]
        finally:
            engine.release.set()
        await asyncio.gather(first.task,second.task,return_exceptions=True)
        assert recipients==[first,None,second,None]
    asyncio.run(scenario())


def test_cancelled_active_job_does_not_fill_default_pool_with_waiters(monkeypatch):
    async def scenario():
        engine=ControlledEngine();service=service_for(engine)
        loop=asyncio.get_running_loop();submit=loop.run_in_executor;submissions=[]
        def tracked(pool,fn,*args):
            if getattr(fn,'__self__',None) is service:
                submissions.append(args[0].run_id)
            return submit(pool,fn,*args)
        monkeypatch.setattr(loop,'run_in_executor',tracked)
        first=await service.create_scan(target_symbol='FIRST',exchange='first')
        queued=[]
        try:
            assert await asyncio.to_thread(engine.started.wait,2)
            service.cancel_job(first.run_id)
            queued=[await service.create_scan(target_symbol='SECOND',exchange='second') for _ in range(20)]
            await asyncio.sleep(.05)
            assert submissions==[first.run_id]
            assert all(job.status=='queued' for job in queued)
        finally:
            engine.release.set()
        await asyncio.gather(first.task,*(job.task for job in queued),return_exceptions=True)
        assert len(submissions)==21 and all(job.status=='completed' for job in queued)
    asyncio.run(scenario())


def isolated_api_handler(name,engine,lock,router,monkeypatch):
    """Run the actual route body without api_server's adapter/bootstrap side effects."""
    from backend.shared.config.scanner_modes import get_mode
    from backend.shared.config.smc_config import SMCConfig
    from backend.analysis import pair_selection
    root=Path(__file__).resolve().parents[3]
    tree=ast.parse((root/'backend/api_server.py').read_text(encoding='utf8'))
    node=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name==name)
    node.decorator_list=[]
    monkeypatch.setattr(pair_selection,'select_symbols',lambda **kwargs:['SECOND'])
    namespace=dict(asyncio=asyncio,orchestrator=engine,orchestrator_lock=lock,
                   Query=router.Query,HTTPException=router.HTTPException,
                   SMCConfigUpdate=router.SMCConfigUpdate,SMCConfig=SMCConfig,get_mode=get_mode,
                   EXCHANGE_ADAPTERS={'second':lambda:SimpleNamespace(name='second')},
                   IngestionPipeline=lambda adapter:None,logger=logging.getLogger(__name__))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'api-handler-fixture','exec'),namespace)
    return namespace[name]


@pytest.mark.parametrize('entrypoint',['signals','smc','debug','legacy_smc'])
def test_all_shared_engine_entrypoints_wait_without_blocking_event_loop(monkeypatch,entrypoint):
    from backend.routers import scanner as router
    from backend.shared.config.smc_config import SMCConfig
    from backend.shared.utils import signal_transform
    async def scenario():
        engine=ControlledEngine();engine.smc_config=SMCConfig()
        changed=[];engine.update_smc_config=lambda cfg:changed.append(cfg)
        lock=threading.Lock();service=service_for(engine,orchestrator_lock=lock)
        monkeypatch.setattr(router,'get_orchestrator',lambda:engine)
        monkeypatch.setattr(router,'get_orchestrator_lock',lambda:lock)
        monkeypatch.setattr(router,'get_exchange_adapters',lambda:{'second':lambda:SimpleNamespace(name='second')})
        monkeypatch.setattr(router,'select_symbols',lambda **kwargs:['SECOND'])
        monkeypatch.setattr(router,'_shared_state',{'IngestionPipeline':lambda adapter:None})
        monkeypatch.setattr(signal_transform,'transform_trade_plans_to_signals',lambda *args:([],[]))
        first=await service.create_scan(target_symbol='FIRST',exchange='first',sniper_mode='overwatch',leverage=2)
        watchdog=threading.Timer(2,engine.release.set)
        operation=None
        try:
            assert await asyncio.to_thread(engine.started.wait,2)
            watchdog.start()
            if entrypoint=='signals':
                call=router.get_signals(limit=1,min_score=0,sniper_mode='strike',majors=True,altcoins=True,meme_mode=False,
                                        exchange='second',leverage=7,macro_overlay=False,market_type='swap',target_symbol=None)
            elif entrypoint=='smc':
                call=router.update_smc_config(router.SMCConfigUpdate(min_wick_ratio=1.5))
            elif entrypoint=='debug':
                call=isolated_api_handler('debug_signals_schema',engine,lock,router,monkeypatch)(limit=1,sniper_mode='strike',exchange='second')
            else:
                call=isolated_api_handler('update_smc_config',engine,lock,router,monkeypatch)(router.SMCConfigUpdate(min_wick_ratio=1.5))
            operation=asyncio.create_task(call)
            await asyncio.sleep(.05)
            assert not engine.release.is_set(),'The API event loop waited for the blocking worker'
            assert not operation.done() and not changed
            assert engine.applied==['overwatch']
        finally:
            engine.release.set();watchdog.cancel()
        result=await operation
        await first.task
        for _,before,after in engine.observed:
            assert before==after
        assert isinstance(result,dict)
        if entrypoint in ('smc','legacy_smc'):
            assert len(changed)==1 and result['status']=='updated'
    asyncio.run(scenario())
