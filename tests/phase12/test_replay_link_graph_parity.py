"""The upstream export parser must not discard a materialized link graph."""


def test_direct_export_dict_preserves_top_level_links():
    from server import _parse_export

    pages = [{"url": "https://example.com/"}]
    links = [{
        "source_url": "https://example.com/",
        "target_url": "https://example.com/about",
        "anchor_text": "About", "is_internal": True,
    }]

    parsed_pages, parsed_links = _parse_export({"pages": pages, "links": links})

    assert parsed_pages == pages
    assert parsed_links == links
