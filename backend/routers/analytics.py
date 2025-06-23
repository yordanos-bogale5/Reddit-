from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel
import logging

from database import get_db
from models import RedditAccount
from karma_service import karma_service
from analytics_engine import analytics_engine
from visualization_service import visualization_service
from export_service import export_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for API responses
class KarmaGrowthResponse(BaseModel):
    total_karma: int
    post_karma: int
    comment_karma: int
    growth_rate_daily: float
    growth_rate_weekly: float
    growth_rate_monthly: float
    peak_growth_day: Optional[str]
    trend_direction: str

class EngagementResponse(BaseModel):
    total_actions: int
    successful_actions: int
    failed_actions: int
    success_rate: float
    actions_by_type: Dict[str, int]
    actions_by_subreddit: Dict[str, int]
    hourly_distribution: Dict[int, int]
    daily_average: float

class PerformanceResponse(BaseModel):
    automation_efficiency: float
    average_response_time: float
    error_rate: float
    uptime_percentage: float
    most_active_hours: List[int]
    best_performing_subreddits: List[str]

class DashboardSummaryResponse(BaseModel):
    total_accounts: int
    total_karma: int
    total_actions_today: int
    success_rate_today: float
    active_automations: int
    alerts_count: int
    top_performing_account: Optional[str]
    recent_activity: List[Dict[str, Any]]

@router.get("/karma-growth/{account_id}", response_model=KarmaGrowthResponse)
async def get_karma_growth(
    account_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """Get karma growth analytics for an account"""
    try:
        metrics = analytics_engine.get_karma_growth_analytics(account_id, days)
        return KarmaGrowthResponse(
            total_karma=metrics.total_karma,
            post_karma=metrics.post_karma,
            comment_karma=metrics.comment_karma,
            growth_rate_daily=metrics.growth_rate_daily,
            growth_rate_weekly=metrics.growth_rate_weekly,
            growth_rate_monthly=metrics.growth_rate_monthly,
            peak_growth_day=metrics.peak_growth_day,
            trend_direction=metrics.trend_direction
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting karma growth: {str(e)}")

@router.get("/engagement/{account_id}", response_model=EngagementResponse)
async def get_engagement_analytics(
    account_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """Get engagement analytics for an account"""
    try:
        metrics = analytics_engine.get_engagement_analytics(account_id, days)
        return EngagementResponse(
            total_actions=metrics.total_actions,
            successful_actions=metrics.successful_actions,
            failed_actions=metrics.failed_actions,
            success_rate=metrics.success_rate,
            actions_by_type=metrics.actions_by_type,
            actions_by_subreddit=metrics.actions_by_subreddit,
            hourly_distribution=metrics.hourly_distribution,
            daily_average=metrics.daily_average
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting engagement analytics: {str(e)}")

@router.get("/performance/{account_id}", response_model=PerformanceResponse)
async def get_performance_analytics(
    account_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """Get performance analytics for an account"""
    try:
        metrics = analytics_engine.get_performance_analytics(account_id, days)
        return PerformanceResponse(
            automation_efficiency=metrics.automation_efficiency,
            average_response_time=metrics.average_response_time,
            error_rate=metrics.error_rate,
            uptime_percentage=metrics.uptime_percentage,
            most_active_hours=metrics.most_active_hours,
            best_performing_subreddits=metrics.best_performing_subreddits
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting performance analytics: {str(e)}")

@router.get("/dashboard-summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    account_id: Optional[int] = Query(None, description="Specific account ID, or all accounts if not provided")
):
    """Get dashboard summary statistics"""
    try:
        summary = analytics_engine.get_dashboard_summary(account_id)
        return DashboardSummaryResponse(**summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting dashboard summary: {str(e)}")

@router.get("/time-series/{account_id}")
async def get_time_series_data(
    account_id: int,
    metric: str = Query(..., description="Metric type: karma, engagement, or activity"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """Get time series data for charts"""
    try:
        if metric not in ['karma', 'engagement', 'activity']:
            raise HTTPException(status_code=400, detail="Invalid metric type")

        data = analytics_engine.get_time_series_data(account_id, metric, days)
        return {"data": data, "metric": metric, "period_days": days}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting time series data: {str(e)}")

@router.get("/subreddit-analytics/{account_id}")
async def get_subreddit_analytics(
    account_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """Get subreddit performance analytics"""
    try:
        analytics = analytics_engine.get_subreddit_analytics(account_id, days)
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting subreddit analytics: {str(e)}")

@router.get("/comparative-analytics")
async def get_comparative_analytics(
    account_ids: List[int] = Query(..., description="List of account IDs to compare"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """Get comparative analytics between multiple accounts"""
    try:
        if len(account_ids) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 accounts can be compared")

        comparison = analytics_engine.get_comparative_analytics(account_ids, days)
        return comparison
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting comparative analytics: {str(e)}")

@router.get("/accounts")
async def get_accounts_list():
    """Get list of all accounts for selection"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        accounts = db.query(RedditAccount).all()
        db.close()

        return [
            {
                "id": account.id,
                "username": account.reddit_username,
                "created_at": account.created_at.isoformat() if account.created_at else None
            }
            for account in accounts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting accounts list: {str(e)}")

@router.get("/export-data/{account_id}")
async def get_export_data(
    account_id: int,
    format: str = Query("json", description="Export format: json or csv"),
    days: int = Query(30, ge=1, le=365, description="Number of days to export")
):
    """Get data for export functionality"""
    try:
        karma_metrics = analytics_engine.get_karma_growth_analytics(account_id, days)
        engagement_metrics = analytics_engine.get_engagement_analytics(account_id, days)
        performance_metrics = analytics_engine.get_performance_analytics(account_id, days)

        export_data = {
            "account_id": account_id,
            "export_date": datetime.utcnow().isoformat(),
            "period_days": days,
            "karma_analytics": {
                "total_karma": karma_metrics.total_karma,
                "post_karma": karma_metrics.post_karma,
                "comment_karma": karma_metrics.comment_karma,
                "growth_rate_daily": karma_metrics.growth_rate_daily,
                "growth_rate_weekly": karma_metrics.growth_rate_weekly,
                "growth_rate_monthly": karma_metrics.growth_rate_monthly,
                "trend_direction": karma_metrics.trend_direction
            },
            "engagement_analytics": {
                "total_actions": engagement_metrics.total_actions,
                "successful_actions": engagement_metrics.successful_actions,
                "success_rate": engagement_metrics.success_rate,
                "daily_average": engagement_metrics.daily_average,
                "actions_by_type": engagement_metrics.actions_by_type,
                "actions_by_subreddit": engagement_metrics.actions_by_subreddit
            },
            "performance_analytics": {
                "automation_efficiency": performance_metrics.automation_efficiency,
                "error_rate": performance_metrics.error_rate,
                "most_active_hours": performance_metrics.most_active_hours,
                "best_performing_subreddits": performance_metrics.best_performing_subreddits
            }
        }

        return {
            "format": format,
            "data": export_data,
            "filename": f"reddit_analytics_{account_id}_{datetime.utcnow().strftime('%Y%m%d')}.{format}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error preparing export data: {str(e)}")

@router.post("/karma/snapshot", summary="Take karma snapshot")
def take_karma_snapshot(account_id: int = Query(...), db: Session = Depends(get_db)):
    """Manually trigger a karma snapshot for an account"""
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Take karma snapshot
        success = karma_service.log_karma_snapshot(account_id)

        if success:
            return {"message": f"Karma snapshot taken successfully for account {account_id}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to take karma snapshot")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error taking karma snapshot: {e}")
        raise HTTPException(status_code=500, detail="Failed to take karma snapshot")

@router.get("/health-check")
async def analytics_health_check():
    """Health check endpoint for analytics service"""
    try:
        # Test database connection
        summary = analytics_engine.get_dashboard_summary()
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "total_accounts": summary.get("total_accounts", 0)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

# Visualization endpoints
@router.get("/charts/karma-growth/{account_id}")
async def get_karma_growth_chart(
    account_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    format: str = Query("chartjs", description="Chart format: chartjs or raw")
):
    """Get karma growth chart data"""
    try:
        chart_config = visualization_service.prepare_karma_growth_chart(account_id, days)

        if format == "chartjs":
            return visualization_service.convert_chart_to_chartjs_format(chart_config)
        else:
            return chart_config

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting karma growth chart: {str(e)}")

@router.get("/charts/engagement/{account_id}")
async def get_engagement_chart(
    account_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    format: str = Query("chartjs", description="Chart format: chartjs or raw")
):
    """Get engagement chart data"""
    try:
        chart_config = visualization_service.prepare_engagement_chart(account_id, days)

        if format == "chartjs":
            return visualization_service.convert_chart_to_chartjs_format(chart_config)
        else:
            return chart_config

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting engagement chart: {str(e)}")

@router.get("/charts/subreddit-performance/{account_id}")
async def get_subreddit_performance_chart(
    account_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    format: str = Query("chartjs", description="Chart format: chartjs or raw")
):
    """Get subreddit performance chart data"""
    try:
        chart_config = visualization_service.prepare_subreddit_performance_chart(account_id, days)

        if format == "chartjs":
            return visualization_service.convert_chart_to_chartjs_format(chart_config)
        else:
            return chart_config

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting subreddit performance chart: {str(e)}")

@router.get("/charts/activity-heatmap/{account_id}")
async def get_activity_heatmap(
    account_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    format: str = Query("chartjs", description="Chart format: chartjs or raw")
):
    """Get activity heatmap data"""
    try:
        chart_config = visualization_service.prepare_activity_heatmap(account_id, days)

        if format == "chartjs":
            return visualization_service.convert_chart_to_chartjs_format(chart_config)
        else:
            return chart_config

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting activity heatmap: {str(e)}")

@router.get("/charts/success-rate-trend/{account_id}")
async def get_success_rate_trend(
    account_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    format: str = Query("chartjs", description="Chart format: chartjs or raw")
):
    """Get success rate trend chart data"""
    try:
        chart_config = visualization_service.prepare_success_rate_trend(account_id, days)

        if format == "chartjs":
            return visualization_service.convert_chart_to_chartjs_format(chart_config)
        else:
            return chart_config

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting success rate trend: {str(e)}")

@router.get("/charts/dashboard-overview")
async def get_dashboard_overview_charts(
    account_id: Optional[int] = Query(None, description="Specific account ID, or all accounts if not provided"),
    format: str = Query("chartjs", description="Chart format: chartjs or raw")
):
    """Get all dashboard overview charts"""
    try:
        charts = visualization_service.prepare_dashboard_overview_charts(account_id)

        if format == "chartjs":
            # Convert all charts to Chart.js format
            chartjs_charts = {}
            for chart_name, chart_config in charts.items():
                chartjs_charts[chart_name] = visualization_service.convert_chart_to_chartjs_format(chart_config)
            return chartjs_charts
        else:
            return charts

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting dashboard overview charts: {str(e)}")

# Export endpoints
@router.get("/export/{account_id}")
async def export_account_data(
    account_id: int,
    format: str = Query("json", description="Export format: json, csv, or pdf"),
    days: int = Query(30, ge=1, le=365, description="Number of days to export")
):
    """Export comprehensive analytics data for an account"""
    try:
        if format not in ['json', 'csv', 'pdf']:
            raise HTTPException(status_code=400, detail="Invalid format. Supported: json, csv, pdf")

        export_result = export_service.export_account_analytics(account_id, format, days)

        return {
            "success": True,
            "export_info": {
                "account_id": account_id,
                "format": format,
                "days": days,
                "filename": export_result["filename"],
                "size": export_result["size"],
                "content_type": export_result["content_type"]
            },
            "download_url": f"/api/analytics/download/{account_id}?format={format}&days={days}",
            "content": export_result["content"] if format == "json" else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting data: {str(e)}")

@router.get("/export/comparative")
async def export_comparative_data(
    account_ids: List[int] = Query(..., description="List of account IDs to compare"),
    format: str = Query("json", description="Export format: json, csv, or pdf"),
    days: int = Query(30, ge=1, le=365, description="Number of days to export")
):
    """Export comparative analytics data for multiple accounts"""
    try:
        if format not in ['json', 'csv', 'pdf']:
            raise HTTPException(status_code=400, detail="Invalid format. Supported: json, csv, pdf")

        if len(account_ids) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 accounts can be compared")

        export_result = export_service.export_comparative_analytics(account_ids, format, days)

        return {
            "success": True,
            "export_info": {
                "account_ids": account_ids,
                "format": format,
                "days": days,
                "filename": export_result["filename"],
                "size": export_result["size"],
                "content_type": export_result["content_type"]
            },
            "download_url": f"/api/analytics/download/comparative?account_ids={','.join(map(str, account_ids))}&format={format}&days={days}",
            "content": export_result["content"] if format == "json" else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting comparative data: {str(e)}")

@router.get("/download/{account_id}")
async def download_account_export(
    account_id: int,
    format: str = Query("json", description="Export format: json, csv, or pdf"),
    days: int = Query(30, ge=1, le=365, description="Number of days to export")
):
    """Download exported analytics data for an account"""
    try:
        from fastapi.responses import Response

        export_result = export_service.export_account_analytics(account_id, format, days)

        return Response(
            content=export_result["content"],
            media_type=export_result["content_type"],
            headers={
                "Content-Disposition": f"attachment; filename={export_result['filename']}"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading export: {str(e)}")

@router.get("/download/comparative")
async def download_comparative_export(
    account_ids: str = Query(..., description="Comma-separated account IDs"),
    format: str = Query("json", description="Export format: json, csv, or pdf"),
    days: int = Query(30, ge=1, le=365, description="Number of days to export")
):
    """Download exported comparative analytics data"""
    try:
        from fastapi.responses import Response

        # Parse account IDs
        account_id_list = [int(id.strip()) for id in account_ids.split(',')]

        if len(account_id_list) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 accounts can be compared")

        export_result = export_service.export_comparative_analytics(account_id_list, format, days)

        return Response(
            content=export_result["content"],
            media_type=export_result["content_type"],
            headers={
                "Content-Disposition": f"attachment; filename={export_result['filename']}"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading comparative export: {str(e)}")