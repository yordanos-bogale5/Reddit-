"""
Data export API endpoints for Reddit automation dashboard
Provides comprehensive export functionality for all data types
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging
from io import StringIO, BytesIO

from database import get_db
from models import RedditAccount, EngagementLog, KarmaLog, ActivityLog, AccountHealth
from export_service import export_service
from analytics_engine import analytics_engine

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class ExportRequest(BaseModel):
    account_ids: List[int]
    format: str = 'json'  # json, csv, pdf
    days: int = 30
    export_type: str = 'analytics'  # analytics, logs, karma, activity, safety, all

class BulkExportRequest(BaseModel):
    account_ids: List[int]
    formats: List[str] = ['json', 'csv']
    days: int = 30
    include_types: List[str] = ['analytics', 'logs', 'karma']

@router.post("/analytics")
async def export_analytics(
    account_id: int,
    format: str = Query('json', description="Export format: json, csv, pdf"),
    days: int = Query(30, description="Number of days to export"),
    db: Session = Depends(get_db)
):
    """
    Export comprehensive analytics for an account
    
    Args:
        account_id: Account to export
        format: Export format (json, csv, pdf)
        days: Number of days to include
        
    Returns:
        Downloadable file with analytics data
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Export analytics
        result = export_service.export_account_analytics(account_id, format, days)
        
        # Return as downloadable file
        content = result['content']
        filename = result['filename']
        content_type = result['content_type']
        
        return Response(
            content=content.encode('utf-8') if isinstance(content, str) else content,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to export analytics")

@router.post("/engagement-logs")
async def export_engagement_logs(
    account_id: int,
    format: str = Query('csv', description="Export format: json, csv"),
    days: int = Query(30, description="Number of days to export"),
    db: Session = Depends(get_db)
):
    """
    Export detailed engagement logs for an account
    
    Args:
        account_id: Account to export
        format: Export format (json, csv)
        days: Number of days to include
        
    Returns:
        Downloadable file with engagement logs
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Export engagement logs
        result = export_service.export_engagement_logs(account_id, format, days)
        
        # Return as downloadable file
        content = result['content']
        filename = result['filename']
        content_type = result['content_type']
        
        return Response(
            content=content.encode('utf-8') if isinstance(content, str) else content,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting engagement logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to export engagement logs")

@router.post("/karma-history")
async def export_karma_history(
    account_id: int,
    format: str = Query('csv', description="Export format: json, csv"),
    days: int = Query(30, description="Number of days to export"),
    db: Session = Depends(get_db)
):
    """
    Export karma history for an account
    
    Args:
        account_id: Account to export
        format: Export format (json, csv)
        days: Number of days to include
        
    Returns:
        Downloadable file with karma history
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Export karma history
        result = export_service.export_karma_history(account_id, format, days)
        
        # Return as downloadable file
        content = result['content']
        filename = result['filename']
        content_type = result['content_type']
        
        return Response(
            content=content.encode('utf-8') if isinstance(content, str) else content,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting karma history: {e}")
        raise HTTPException(status_code=500, detail="Failed to export karma history")

@router.post("/activity-logs")
async def export_activity_logs(
    account_id: int,
    format: str = Query('csv', description="Export format: json, csv"),
    days: int = Query(30, description="Number of days to export"),
    db: Session = Depends(get_db)
):
    """
    Export activity logs for an account
    
    Args:
        account_id: Account to export
        format: Export format (json, csv)
        days: Number of days to include
        
    Returns:
        Downloadable file with activity logs
    """
    try:
        from datetime import datetime, timedelta
        import csv
        import json
        
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get activity logs
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        logs = db.query(ActivityLog).filter(
            ActivityLog.account_id == account_id,
            ActivityLog.timestamp >= cutoff_date
        ).order_by(ActivityLog.timestamp.desc()).all()
        
        if format == 'csv':
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Timestamp', 'Action', 'Details'])
            
            # Write data
            for log in logs:
                writer.writerow([
                    log.timestamp.isoformat(),
                    log.action,
                    json.dumps(log.details) if log.details else ''
                ])
            
            content = output.getvalue()
            output.close()
            content_type = 'text/csv'
            filename = f"activity_logs_{account.reddit_username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            
        else:  # json
            logs_data = []
            for log in logs:
                logs_data.append({
                    'id': log.id,
                    'timestamp': log.timestamp.isoformat(),
                    'action': log.action,
                    'details': log.details
                })
            
            export_data = {
                'export_info': {
                    'username': account.reddit_username,
                    'export_date': datetime.utcnow().isoformat(),
                    'period_days': days,
                    'total_logs': len(logs_data)
                },
                'activity_logs': logs_data
            }
            
            content = json.dumps(export_data, indent=2, default=str)
            content_type = 'application/json'
            filename = f"activity_logs_{account.reddit_username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        return Response(
            content=content.encode('utf-8'),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting activity logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to export activity logs")

@router.post("/safety-reports")
async def export_safety_reports(
    account_id: int,
    format: str = Query('json', description="Export format: json, csv"),
    days: int = Query(30, description="Number of days to export"),
    db: Session = Depends(get_db)
):
    """
    Export safety reports and alerts for an account
    
    Args:
        account_id: Account to export
        format: Export format (json, csv)
        days: Number of days to include
        
    Returns:
        Downloadable file with safety reports
    """
    try:
        from datetime import datetime, timedelta
        from safety_tasks import get_safety_status, get_safety_alerts
        import csv
        import json
        
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get safety data
        safety_status = get_safety_status(account_id)
        safety_alerts = get_safety_alerts(account_id, days * 24)  # Convert days to hours
        
        # Get account health
        health = account.account_health
        health_data = {
            'trust_score': health.trust_score if health else 0,
            'account_age_days': health.account_age_days if health else 0,
            'shadowbanned': health.shadowbanned if health else False,
            'login_issues': health.login_issues if health else False,
            'captcha_triggered': health.captcha_triggered if health else False,
            'bans': health.bans if health else 0,
            'deletions': health.deletions if health else 0,
            'removals': health.removals if health else 0
        } if health else {}
        
        if format == 'csv':
            output = StringIO()
            writer = csv.writer(output)
            
            # Safety status section
            writer.writerow(['SAFETY STATUS'])
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Is Safe', safety_status.get('is_safe', False)])
            writer.writerow(['Trust Score', health_data.get('trust_score', 0)])
            writer.writerow(['Shadowbanned', health_data.get('shadowbanned', False)])
            writer.writerow(['Login Issues', health_data.get('login_issues', False)])
            writer.writerow(['Captcha Triggered', health_data.get('captcha_triggered', False)])
            writer.writerow([])
            
            # Safety alerts section
            writer.writerow(['SAFETY ALERTS'])
            writer.writerow(['Timestamp', 'Alert Type', 'Severity', 'Message'])
            for alert in safety_alerts:
                writer.writerow([
                    alert.get('timestamp', ''),
                    alert.get('alert_type', ''),
                    alert.get('severity', ''),
                    alert.get('message', '')
                ])
            
            content = output.getvalue()
            output.close()
            content_type = 'text/csv'
            filename = f"safety_report_{account.reddit_username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            
        else:  # json
            export_data = {
                'export_info': {
                    'username': account.reddit_username,
                    'export_date': datetime.utcnow().isoformat(),
                    'period_days': days
                },
                'safety_status': safety_status,
                'account_health': health_data,
                'safety_alerts': safety_alerts
            }
            
            content = json.dumps(export_data, indent=2, default=str)
            content_type = 'application/json'
            filename = f"safety_report_{account.reddit_username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        return Response(
            content=content.encode('utf-8'),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting safety reports: {e}")
        raise HTTPException(status_code=500, detail="Failed to export safety reports")

@router.post("/complete-export")
async def export_complete_account_data(
    account_id: int,
    format: str = Query('json', description="Export format: json, csv"),
    days: int = Query(30, description="Number of days to export"),
    db: Session = Depends(get_db)
):
    """
    Export complete account data including all logs, analytics, and reports
    
    Args:
        account_id: Account to export
        format: Export format (json, csv)
        days: Number of days to include
        
    Returns:
        Downloadable file with complete account data
    """
    try:
        from datetime import datetime, timedelta
        import zipfile
        import tempfile
        import os
        
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Create temporary directory for files
        with tempfile.TemporaryDirectory() as temp_dir:
            files_created = []
            
            try:
                # Export analytics
                analytics_result = export_service.export_account_analytics(account_id, format, days)
                analytics_path = os.path.join(temp_dir, analytics_result['filename'])
                with open(analytics_path, 'w', encoding='utf-8') as f:
                    f.write(analytics_result['content'])
                files_created.append((analytics_path, analytics_result['filename']))
                
                # Export engagement logs
                engagement_result = export_service.export_engagement_logs(account_id, format, days)
                engagement_path = os.path.join(temp_dir, engagement_result['filename'])
                with open(engagement_path, 'w', encoding='utf-8') as f:
                    f.write(engagement_result['content'])
                files_created.append((engagement_path, engagement_result['filename']))
                
                # Export karma history
                karma_result = export_service.export_karma_history(account_id, format, days)
                karma_path = os.path.join(temp_dir, karma_result['filename'])
                with open(karma_path, 'w', encoding='utf-8') as f:
                    f.write(karma_result['content'])
                files_created.append((karma_path, karma_result['filename']))
                
            except Exception as e:
                logger.warning(f"Some exports failed: {e}")
            
            # Create ZIP file
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path, filename in files_created:
                    zip_file.write(file_path, filename)
            
            zip_buffer.seek(0)
            zip_content = zip_buffer.getvalue()
            zip_buffer.close()
            
            zip_filename = f"complete_export_{account.reddit_username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
            
            return Response(
                content=zip_content,
                media_type='application/zip',
                headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating complete export: {e}")
        raise HTTPException(status_code=500, detail="Failed to create complete export")
