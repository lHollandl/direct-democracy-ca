"""The opt-in live check (ARCHITECTURE.md §10): `pytest -m live`.

Everything else mocks Ollama through the client interface. This one test asks
the real model, on the real prompt files, whether the output still has the shape
the code parses — which is the thing a mock can never tell you.
"""

from __future__ import annotations

import pytest

from backend.clients import ollama as ollama_client


@pytest.mark.live
async def test_the_labeler_prompt_still_produces_the_shape_the_code_parses():
    client = ollama_client.OllamaClient()
    raw, prompt = await client.generate(
        "labeler.md",
        {
            "problem_text": (
                "The intersection near Washington Elementary has no marked crosswalk and "
                "children cross four lanes of traffic to reach the school."
            ),
            "categories": "- Public Safety\n- Roads and Infrastructure\n- Education",
            "communities": (
                "### San Jose (city)\n"
                "community_level: city\n"
                "community_entity_id: 408\n"
                "7 | Pedestrian Safety Near Schools | Crossings near schools are unsafe.\n"
                "9 | Road Damage and Pothole Repair | Streets have potholes.\n"
            ),
        },
    )
    assert prompt.output_format, "the prompt file declares the JSON shape it expects back"
    parsed = ollama_client.parse_json_output(raw)
    assert isinstance(parsed["main_category"], str)
    assert isinstance(parsed["umbrellas"], list)
    assert 0.0 <= float(parsed["confidence"]) <= 1.0
    for entry in parsed["umbrellas"]:
        assert set(entry) >= {"community_level", "community_entity_id", "umbrella_id"}


@pytest.mark.live
async def test_embeddings_come_back_the_same_length_and_compare_sensibly():
    client = ollama_client.OllamaClient()
    one = await client.embed("Paint a crosswalk and install a refuge island in the median.")
    two = await client.embed("Add a refuge island in the median and paint a crosswalk.")
    three = await client.embed("Increase the frequency of buses on the weekend timetable.")
    assert len(one) == len(two) == len(three)
    near = ollama_client.cosine_similarity(one, two)
    far = ollama_client.cosine_similarity(one, three)
    assert near > far, "two ways of saying the same change must score closer than two topics"
