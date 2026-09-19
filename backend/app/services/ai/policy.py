"""Every externally callable AI operation requires an explicit credit policy."""
from dataclasses import dataclass
from app.services.ai.errors import AIError


@dataclass(frozen=True)
class OperationPolicy:
    credits: int
    purpose: str


OPERATIONS = {
    'exam_generation': OperationPolicy(10, 'Full exam including child calls'),
    'question_generation': OperationPolicy(10, 'Standalone question generation'),
    'question_regeneration': OperationPolicy(1, 'Selected question repair'),
    'answer_generation': OperationPolicy(2, 'Standalone answers'),
    'exam_review': OperationPolicy(5, 'Standalone AI review'),
    'question_edit': OperationPolicy(1, 'Verify teacher revision'),
    'matrix_generation': OperationPolicy(0, 'Pilot explicitly free matrix'),
    'specification_generation': OperationPolicy(0, 'Pilot explicitly free specification'),
    'document_upload': OperationPolicy(0, 'Pilot explicitly free extraction/OCR'),
    'rag_query': OperationPolicy(0, 'Pilot explicitly free retrieval/embedding'),
    'rag_index': OperationPolicy(0, 'Pilot explicitly free indexing'),
    'bank_search': OperationPolicy(0, 'Pilot explicitly free semantic search'),
    'provider_test': OperationPolicy(0, 'Operator diagnostic, measured and limited'),
}


def operation_policy(operation):
    policy = OPERATIONS.get(operation)
    if policy is None or type(policy.credits) is not int or policy.credits < 0:
        raise AIError('AI_OPERATION_NOT_CONFIGURED', 503)
    return policy
