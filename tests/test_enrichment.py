from intelligence.enrichment import confidence_score, detect_opportunities, extract_entities, trend_signals


def test_entities_opportunities_and_trends_are_deterministic():
    item = {
        "title": "OpenAI funding for AI agents in India",
        "text": "OpenAI announced a grant and an AI agent program for India.",
        "url": "https://example.test/story",
        "priority": 8,
    }
    analysis = {"facts": ["confirmed"], "interpretation": ["Check official details"], "confidence": 0.8}
    entities = extract_entities(item["title"] + " " + item["text"])
    assert {entity["name"] for entity in entities} >= {"OpenAI", "India", "AI"}
    opportunities = detect_opportunities(item, analysis)
    assert opportunities[0]["type"] in {"grant", "funding"}
    assert opportunities[0]["deadline"] == "unknown"
    assert confidence_score(item, analysis, 2) > 0.4
    assert trend_signals([{"topics": ["ai"], "entities": entities}, {"topics": ["ai"], "entities": entities}])
