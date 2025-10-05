from pydantic import BaseModel, Extra

class SDP(BaseModel):
    sdp: str
    type: str

class EventPayload(BaseModel):
    class Config:
        extra = Extra.allow