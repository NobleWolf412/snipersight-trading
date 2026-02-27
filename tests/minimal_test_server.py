"""
Minimal test server to diagnose the issue.
"""
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn

app = FastAPI()

# Simple in-memory storage
notifications = []

class SimpleNotification(BaseModel):
    type: str
    priority: str = "medium"
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/test")
async def test():
    return {"status": "ok"}

@app.post("/send")
async def send_notification(notification: SimpleNotification):
    import uuid
    from datetime import datetime, timezone
    
    new_notif = {
        "id": str(uuid.uuid4()),
        "type": notification.type,
        "priority": notification.priority,
        "title": notification.title,
        "message": notification.message,
        "data": notification.data or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "read": False
    }
    
    notifications.append(new_notif)
    return {"success": True, "notification_id": new_notif["id"]}

@app.get("/notifications")
async def get_notifications():
    return {"notifications": notifications}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")