import { Link } from 'react-router-dom';
import { FooterStatus, PageHead } from '@/components/hud';
const tools = [
  {path:'/training/lessons',title:'Lessons',description:'Read and resume nine strategy chapters. Historical examples are labeled.'},
  {path:'/training/replay',title:'Historical replay',description:'Inspect historical candles and causal evidence. Missing historical inputs remain explicit.'},
  {path:'/training/range',title:'Paper session',description:'Configure or monitor simulated execution, with separate paper accounting.'},
  {path:'/training/drills',title:'Research tools',description:'Experimental model controls and attribution. Research results are not trading probabilities.'},
];
export function TrainingGround() {
  return <div className="page"><PageHead title="Training" subtitle="Choose a learning or research tool" />
    <nav className="training-tools" aria-label="Learning and research tools">{tools.map(tool=><Link key={tool.path} to={tool.path}><h2>{tool.title}</h2><p>{tool.description}</p><span>Open →</span></Link>)}</nav>
    <FooterStatus />
  </div>;
}
