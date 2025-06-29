from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class Event(BaseModel):
    """Represents a single parsed middleware event."""

    event_id: int = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(..., description="Event timestamp")
    operator_id: str = Field(..., description="Operator identifier")
    location: str = Field(..., description="Location where test performed")
    device_id: str = Field(..., description="Device identifier")
    test_type: str = Field(..., description="Type of test performed")
    rapid: bool = Field(False, description="Rapid repeat test flag")
    loc_conflict: bool = Field(False, description="Location conflict flag")
    device_hop: bool = Field(False, description="Device hopping flag")
    shift_viol: bool = Field(False, description="Shift violation flag")
    load_dev: bool = Field(False, description="High device load flag")
    coloc: bool = Field(False, description="Device co-location flag")
    flagged: bool = Field(False, description="Any flag triggered")

class OperatorSummary(BaseModel):
    operator_id: str
    total_tests: int
    suspicion_score: float
    rapid_count: int
    loc_conflict_count: int
    device_hop_count: int
    shift_viol_count: int
    load_dev_count: int
    coloc_count: int

class DeviceSummary(BaseModel):
    device_id: str
    total_tests: int
    unique_users: int
    coloc_events: int

class FlagStats(BaseModel):
    rapid: int
    loc_conflict: int
    device_hop: int
    shift_viol: int
    load_dev: int
    coloc: int

class UsageSummary(BaseModel):
    """Main response model returned after analysis."""

    flagged_events_preview: List[Event]
    operator_summary: List[OperatorSummary]
    device_summary: List[DeviceSummary]
    flag_stats: FlagStats
    hourly_heatmap_matrix: Dict[str, Dict[str, int]]
    insights: Optional[Dict[str, List[str]]] = None
