from pydantic import BaseModel


class ResearchBase(BaseModel):
    research_id: int
    research_name: str


class ResearchCard(ResearchBase):
    research_version_name: str
    research_last_update_time: str
    schedule_next_launch_time: str


class NearestResearch(ResearchBase):
    schedule_next_launch_time: str
