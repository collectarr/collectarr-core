from app.services.importers.clz.clz_comics_xml_importer import ClzComicsXmlImporter


def test_clz_comics_xml_importer_parses_creator_and_character_fields() -> None:
    xml = """
    <Comic>
      <Title>Sample Issue</Title>
      <Series>Sample Series</Series>
      <Number>12</Number>
      <Creators>
        <Creator>
          <Name>Jane Doe</Name>
          <Role>Penciller</Role>
          <RoleId>dfArtist</RoleId>
          <Sequence>1</Sequence>
          <SortName>Doe, Jane</SortName>
          <ImageUrl>https://example.com/jane.jpg</ImageUrl>
          <CoreId>123</CoreId>
          <ImdbNameId>nm456</ImdbNameId>
        </Creator>
      </Creators>
      <Characters>
        <Character>
          <Name>Hero</Name>
          <Role>featured</Role>
          <SortName>Hero</SortName>
        </Character>
      </Characters>
    </Comic>
    """

    record = ClzComicsXmlImporter().parse(xml)[0]

    assert record.title == "Sample Issue"
    assert record.creators[0].role_id == "dfArtist"
    assert record.creators[0].external_ids == {"clz_core_id": "123", "imdb_name_id": "nm456"}
    assert record.characters[0].name == "Hero"
