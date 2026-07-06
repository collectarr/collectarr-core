from app.services.importers.clz.clz_music_xml_importer import ClzMusicXmlImporter


def test_clz_music_xml_importer_parses_disc_track_and_credit_fields() -> None:
    xml = """
    <Music>
      <Title>Sample Album</Title>
      <Label>Sample Label</Label>
      <CatalogNumber>CAT-001</CatalogNumber>
      <UPC>123456789012</UPC>
      <TrackCount>2</TrackCount>
      <DiscCount>1</DiscCount>
      <Credits>
        <Credit>
          <Name>Jane Artist</Name>
          <Role>Artist</Role>
          <RoleId>artist</RoleId>
          <Sequence>1</Sequence>
        </Credit>
      </Credits>
      <Disc>
        <DiscNumber>1</DiscNumber>
        <Title>Disc 1</Title>
        <TrackCount>2</TrackCount>
        <TOC>1 2 3</TOC>
        <CDDBId>cddb-1</CDDBId>
        <LeadoutOffset>12345</LeadoutOffset>
        <BPDiscId>bp-1</BPDiscId>
        <Tracks>
          <Track>
            <Position>1</Position>
            <Title>Intro</Title>
            <DurationMs>1000</DurationMs>
            <OffsetMs>0</OffsetMs>
            <BitrateKbps>320</BitrateKbps>
            <FileSizeBytes>1024</FileSizeBytes>
            <Hash>hash-1</Hash>
          </Track>
        </Tracks>
      </Disc>
    </Music>
    """

    record = ClzMusicXmlImporter().parse(xml)[0]

    assert record.title == "Sample Album"
    assert record.publisher == "Sample Label"
    assert record.upc == "123456789012"
    assert record.credits[0].role_id == "artist"
    assert record.discs[0].cddb_id == "cddb-1"
    assert record.discs[0].tracks[0].track_hash == "hash-1"
