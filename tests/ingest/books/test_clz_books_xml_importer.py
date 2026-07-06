from app.services.importers.clz.clz_books_xml_importer import ClzBooksXmlImporter


def test_clz_books_xml_importer_parses_creator_and_book_fields() -> None:
    xml = """
    <Books>
      <Book>
        <Title>Sample Book</Title>
        <Series>Sample Series</Series>
        <Number>7</Number>
        <Publisher>Sample Publisher</Publisher>
        <OriginalPublisher>Original Publisher</OriginalPublisher>
        <OriginalLanguage>en</OriginalLanguage>
        <OriginalPublicationDate>2001-05-01</OriginalPublicationDate>
        <Dewey>813.54</Dewey>
        <LCCN>2001023456</LCCN>
        <LocControlNumber>loc-123</LocControlNumber>
        <Format>Hardcover</Format>
        <Dimensions>6 x 9 in</Dimensions>
        <DustJacket>yes</DustJacket>
        <Printing>First printing</Printing>
        <FirstEdition>true</FirstEdition>
        <NumberLine>1 2 3 4</NumberLine>
        <LocalCoverImagePath>C:\\covers\\front.jpg</LocalCoverImagePath>
        <LocalBackImagePath>C:\\covers\\back.jpg</LocalBackImagePath>
        <LocalThumbnailImagePath>C:\\covers\\thumb.jpg</LocalThumbnailImagePath>
        <Creators>
          <Creator>
            <Name>Jane Author</Name>
            <Role>Author</Role>
            <RoleId>author</RoleId>
            <Sequence>1</Sequence>
            <SortName>Author, Jane</SortName>
            <ImageUrl>https://example.com/jane.jpg</ImageUrl>
            <Biography>Writer of sample books.</Biography>
            <CoreId>123</CoreId>
            <ImdbNameId>nm456</ImdbNameId>
          </Creator>
        </Creators>
      </Book>
    </Books>
    """

    record = ClzBooksXmlImporter().parse(xml)[0]

    assert record.title == "Sample Book"
    assert record.original_publisher == "Original Publisher"
    assert record.dewey == "813.54"
    assert record.dust_jacket is True
    assert record.creators[0].role_id == "author"
    assert record.creators[0].biography == "Writer of sample books."
