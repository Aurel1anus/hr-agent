from enum import Enum

class JobStatus(str, Enum): DRAFT="draft"; ACTIVE="active"; PAUSED="paused"; CLOSED="closed"
class PipelineStage(str, Enum):
    SCREENING="screening"; CONTACTING="contacting"; READY_TO_SUBMIT="ready_to_submit"; INTERVIEWER_REVIEW="interviewer_review"; SCHEDULING="scheduling"; INTERVIEW_SCHEDULED="interview_scheduled"; FEEDBACK_PENDING="feedback_pending"; DECISION_PENDING="decision_pending"; OFFER="offer"; REJECTED="rejected"; WITHDRAWN="withdrawn"; ON_HOLD="on_hold"
class BlockedBy(str, Enum): NONE="none"; HR="hr"; CANDIDATE="candidate"; INTERVIEWER="interviewer"; SYSTEM="system"
class TaskStatus(str, Enum): TODO="todo"; DONE="done"; CANCELLED="cancelled"
class Priority(str, Enum): LOW="low"; NORMAL="normal"; HIGH="high"
class InterviewMode(str, Enum): ONLINE="online"; OFFLINE="offline"
class InterviewStatus(str, Enum): SCHEDULED="scheduled"; COMPLETED="completed"; CANCELLED="cancelled"
class ResumeParseStatus(str, Enum): UPLOADED="uploaded"; PARSED="parsed"; CONFIRMED="confirmed"
