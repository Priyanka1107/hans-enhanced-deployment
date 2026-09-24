from app.email.service import _build_topic_evidence_map


def test_topic_evidence_map_preserves_final_doc_numbers():
    doc_a = {
        "id": "doc-a",
        "title": "Applying",
    }
    doc_b = {
        "id": "doc-b",
        "title": "Required documents",
    }
    doc_c = {
        "id": "doc-c",
        "title": "Language proof",
    }
    doc_not_selected = {
        "id": "doc-not-selected",
        "title": "Unused evidence",
    }

    topics = [
        {
            "topic_id": "application_deadline",
            "label": "Application deadline",
        },
        {
            "topic_id": "required_documents",
            "label": "Required documents",
        },
    ]

    topic_document_groups = [
        [
            doc_b,
            doc_a,
            doc_not_selected,
        ],
        [
            doc_c,
            doc_b,
            doc_b,
        ],
    ]

    final_documents = [
        doc_a,
        doc_b,
        doc_c,
    ]

    result = _build_topic_evidence_map(
        topics=topics,
        topic_document_groups=topic_document_groups,
        final_documents=final_documents,
    )

    assert result == [
        {
            "topic_id": "application_deadline",
            "label": "Application deadline",
            "doc_numbers": [2, 1],
        },
        {
            "topic_id": "required_documents",
            "label": "Required documents",
            "doc_numbers": [3, 2],
        },
    ]
