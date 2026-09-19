from types import SimpleNamespace

from app.services.exam_service import ExamService


def test_exam_variants_follow_teacher_count_and_variant_rules():
    service = ExamService()
    exam = SimpleNamespace(
        id=99,
        resource_package={"variant_count": 6},
        questions=[
            {
                "id": "q_1",
                "number": 1,
                "type": "multiple_choice",
                "difficulty": "nhan_biet",
                "score": 0.25,
                "content": "Câu hỏi trắc nghiệm 1",
                "options": {
                    "A": "Đáp án đúng",
                    "B": "Nhiễu 1",
                    "C": "Nhiễu 2",
                    "D": "Nhiễu 3",
                },
                "metadata": {},
            },
            {
                "id": "q_2",
                "number": 2,
                "type": "multiple_choice",
                "difficulty": "thong_hieu",
                "score": 0.25,
                "content": "Câu hỏi trắc nghiệm 2",
                "options": {
                    "A": "Nhiễu 1",
                    "B": "Đáp án đúng",
                    "C": "Nhiễu 2",
                    "D": "Nhiễu 3",
                },
                "metadata": {},
            },
            {
                "id": "q_3",
                "number": 3,
                "type": "true_false",
                "difficulty": "thong_hieu",
                "score": 0.5,
                "content": "Câu đúng sai",
                "statements": [
                    {"id": "s_1", "content": "Phát biểu 1", "is_true": True},
                    {"id": "s_2", "content": "Phát biểu 2", "is_true": False},
                    {"id": "s_3", "content": "Phát biểu 3", "is_true": True},
                    {"id": "s_4", "content": "Phát biểu 4", "is_true": False},
                ],
                "metadata": {},
            },
            {
                "id": "q_4",
                "number": 4,
                "type": "essay",
                "difficulty": "van_dung",
                "score": 2.5,
                "content": "Câu tự luận",
                "sub_questions": [
                    {"id": "q_4_a", "content": "Ý 1", "score": 1.5},
                    {"id": "q_4_b", "content": "Ý 2", "score": 1.0},
                ],
                "metadata": {},
            },
        ],
        answer_key=[
            {
                "question_id": "q_1",
                "question_number": 1,
                "type": "multiple_choice",
                "correct_answer": "A",
            },
            {
                "question_id": "q_2",
                "question_number": 2,
                "type": "multiple_choice",
                "correct_answer": "B",
            },
            {
                "question_id": "q_3",
                "question_number": 3,
                "type": "true_false",
                "answers": [
                    {"statement_id": "s_1", "is_true": True, "explanation": ""},
                    {"statement_id": "s_2", "is_true": False, "explanation": ""},
                    {"statement_id": "s_3", "is_true": True, "explanation": ""},
                    {"statement_id": "s_4", "is_true": False, "explanation": ""},
                ],
            },
            {
                "question_id": "q_4",
                "question_number": 4,
                "type": "essay",
                "model_answer": "Học sinh trình bày đúng ý.",
                "key_points": ["Ý chính"],
            },
        ],
    )

    variants = service._build_variants(exam)

    assert [variant["code"] for variant in variants] == ["101", "102", "103", "104", "105", "106"]
    assert all(len(variant["questions"]) == 4 for variant in variants)

    original_options = {
        question["id"]: question["options"]
        for question in exam.questions
        if question["type"] == "multiple_choice"
    }
    original_answers = {
        answer["question_id"]: answer["correct_answer"]
        for answer in exam.answer_key
        if answer["type"] == "multiple_choice"
    }
    mc_orders = []
    true_false_contents = []
    essay_contents = []

    for variant in variants:
        variant_questions = variant["questions"]
        variant_answers = {
            answer["original_question_id"]: answer
            for answer in variant["answer_key"]
        }
        multiple_choice_questions = [
            question for question in variant_questions
            if question["type"] == "multiple_choice"
        ]
        mc_orders.append(tuple(question["original_id"] for question in multiple_choice_questions))

        for question in multiple_choice_questions:
            original_id = question["original_id"]
            assert sorted(question["options"].values()) == sorted(original_options[original_id].values())
            correct = variant_answers[original_id]["correct_answer"]
            assert question["options"][correct] == original_options[original_id][original_answers[original_id]]
            assert question["correct_answer"] == correct

        true_false_question = [
            question for question in variant_questions
            if question["type"] == "true_false"
        ][0]
        true_false_contents.append(true_false_question["content"])
        assert all(statement["id"].startswith(true_false_question["id"]) for statement in true_false_question["statements"])
        assert [
            item["is_true"]
            for item in variant_answers["q_3"]["answers"]
        ] == [
            statement["is_true"]
            for statement in true_false_question["statements"]
        ]

        essay_question = [
            question for question in variant_questions
            if question["type"] == "essay"
        ][0]
        essay_contents.append(essay_question["content"])
        assert [s["content"] for s in essay_question["sub_questions"]] == ["Ý 1", "Ý 2"]
        assert variant_answers["q_4"]["model_answer"] == "Học sinh trình bày đúng ý."
        assert variant_answers["q_4"]["key_points"] == ["Ý chính"]
        assert {s["content"] for s in true_false_question["statements"]} == {"Phát biểu 1", "Phát biểu 2", "Phát biểu 3", "Phát biểu 4"}

    assert len(set(mc_orders)) > 1
    assert set(true_false_contents) == {"Câu đúng sai"}
    assert set(essay_contents) == {"Câu tự luận"}


def test_option_shuffle_is_deterministic_and_remaps_answer_explanations():
    from copy import deepcopy
    from app.services.exam.variants import build_variants
    question = {'id': 'q', 'number': 1, 'type': 'multiple_choice', 'content': 'Tính tốc độ', 'options': {'A': '1 m/s', 'B': '5 m/s', 'C': '10 m/s', 'D': '20 m/s'}, 'correct_answer': 'B', 'rich_content': [{'type': 'latex', 'content': r'v=\frac{s}{t}'}]}
    answer = {'question_id': 'q', 'correct_answer': 'B', 'explanation': 'Đáp án B đúng vì v = s/t.', 'option_explanations': {key: value + ' explanation' for key, value in question['options'].items()}}
    exam = SimpleNamespace(id=321, questions=[question], answer_key=[answer], resource_package={'variant_count': 12})
    before = deepcopy(exam)
    variants = build_variants(exam)
    assert variants == build_variants(exam)
    labels = set()
    for variant in variants:
        q, a = variant['questions'][0], variant['answer_key'][0]
        labels.add(a['correct_answer'])
        assert q['options'][a['correct_answer']] == '5 m/s'
        assert q['correct_answer'] == a['correct_answer']
        assert a['explanation'].startswith('Đáp án ' + a['correct_answer'])
        assert q['rich_content'] == question['rich_content']
        for key, value in q['options'].items():
            assert a['option_explanations'][key] == value + ' explanation'
    assert len(labels) > 1 and exam == before


def test_tf_shuffle_preserves_truth_explanation_and_statement_identity():
    from app.services.exam.variants import build_variants
    statements = [{'id': f's{i}', 'content': f'Phát biểu {i}', 'is_true': i % 2 == 0} for i in range(4)]
    answers = [{'statement_id': s['id'], 'is_true': s['is_true'], 'explanation': f"Giải thích {s['content']}", 'rubric': {'score': .25}} for s in statements]
    exam = SimpleNamespace(id=99, questions=[{'id': 'q', 'number': 1, 'type': 'true_false', 'statements': statements}], answer_key=[{'question_id': 'q', 'answers': answers}], resource_package={'variant_count': 5})
    for variant in build_variants(exam):
        keyed = {a['statement_id']: a for a in variant['answer_key'][0]['answers']}
        for statement in variant['questions'][0]['statements']:
            answer = keyed[statement['id']]
            assert answer['is_true'] == statement['is_true']
            assert answer['explanation'] == f"Giải thích {statement['content']}"
            assert answer['rubric']['score'] == .25
