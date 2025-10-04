from pydantic import BaseModel

class SDPModel( BaseModel ):
    sdp:    str
    type:   str
