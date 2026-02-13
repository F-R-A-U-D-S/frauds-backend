from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models import User, ExportToken
from datetime import datetime, timedelta

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)


# Track server start time
START_TIME = datetime.now()

@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        # current_user is a dict from get_current_user
        if not current_user.get("is_admin"):
            raise HTTPException(status_code=403, detail="Not authorized")

        # Real data: Total Users
        total_users = db.query(User).count()

        # Real data: Active Users (Logged in within last hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        active_user_count = db.query(User).filter(
            User.last_login_at >= one_hour_ago
        ).filter(
            (User.last_logout_at == None) | (User.last_logout_at < User.last_login_at)
        ).count()

        # Real data: Pending Downloads (Proxy for Pending Reviews)
        pending_download_count = db.query(ExportToken).filter(ExportToken.is_used == False).count()
        
        # Real data: Recent Activity
        # 1. Recent Users
        recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()
        user_activities = [
            {
                "user": u.name or u.username,
                "action": "Joined F.R.A.U.D.S",
                "time": u.created_at,  # Keep as object for sorting
                "avatar": (u.name or u.username)[0].upper()
            }
            for u in recent_users
        ]

        # 2. Recent Exports (Tokens)
        # We need to join with User to get names, or just use user_id if not efficient
        # For now, let's try to fetch user names if possible, or fallback to "User"
        recent_tokens = db.query(ExportToken).order_by(ExportToken.created_at.desc()).limit(5).all()
        token_activities = []
        for t in recent_tokens:
            # Simple lookup (lazy loading might be slow but okay for small N)
            u = db.query(User).filter(User.employee_number == t.user_id).first()
            # Note: ExportToken.user_id seems to store employee_number or ID string?
            # Checking models.py: user_id = Column(String). 
            # In export.py (not visible here but assumed), it likely stores user ID or username.
            # Let's assume it stores 'sub' which is ID.
            if not u:
                 # Try generic lookup
                 u = db.query(User).filter(User.id == t.user_id).first()
            
            user_name = u.name if u else "Unknown User"
            token_activities.append({
                "user": user_name,
                "action": "Requested Export",
                "time": t.created_at,
                "avatar": user_name[0].upper()
            })

        # 3. Recent Logins
        recent_logins = db.query(User).filter(User.last_login_at != None).order_by(User.last_login_at.desc()).limit(5).all()
        login_activities = [
            {
                "user": u.name or u.username,
                "action": "Logged in",
                "time": u.last_login_at,
                "avatar": (u.name or u.username)[0].upper()
            }
            for u in recent_logins
        ]

        # 4. Recent Logouts
        recent_logouts = db.query(User).filter(User.last_logout_at != None).order_by(User.last_logout_at.desc()).limit(5).all()
        logout_activities = [
            {
                "user": u.name or u.username,
                "action": "Logged out",
                "time": u.last_logout_at,
                "avatar": (u.name or u.username)[0].upper()
            }
            for u in recent_logouts
        ]

        # Merge and Sort
        all_activities = user_activities + token_activities + login_activities + logout_activities
        all_activities.sort(key=lambda x: x['time'], reverse=True)
        all_activities = all_activities[:5]

        # Post-process time to string (e.g. "2 mins ago")
        # Helper for relative time (DB stores UTC)
        now_utc = datetime.utcnow()
        def time_ago(dt):
            if not dt: return ""
            diff = now_utc - dt
            if diff.days > 0:
                return f"{diff.days} days ago"
            seconds = diff.seconds
            if seconds < 60:
                return "Just now"
            if seconds < 3600:
                return f"{seconds // 60} mins ago"
            return f"{seconds // 3600} hours ago"

        final_activity_list = []
        for item in all_activities:
            item['time'] = time_ago(item['time'])
            final_activity_list.append(item)


        # Calculate Uptime (Server time is local/system time)
        now_local = datetime.now()
        uptime_duration = now_local - START_TIME
        days = uptime_duration.days
        hours, remainder = divmod(uptime_duration.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        uptime_str = ""
        if days > 0:
            uptime_str += f"{days}d "
        if hours > 0:
            uptime_str += f"{hours}h "
        uptime_str += f"{minutes}m"

        # Estimate Database Load (simple heuristic based on user count)
        if total_users > 10000:
            db_load = "High"
        elif total_users > 1000:
            db_load = "Medium"
        else:
            db_load = "Low"

        return {
            "total_users": total_users,
            "active_sessions": active_user_count,
            "pending_reviews": pending_download_count,
            "recent_activity": final_activity_list,
            "system_status": {
                "uptime": uptime_str,
                "db_load": db_load,
                "security_level": "High" # Placeholder
            }
        }
    except Exception as e:
        print(f"ERROR in get_admin_stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
