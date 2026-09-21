from pathlib import Path

from middleout_lattice.corpus import CorpusStore, compress_corpus, decompress_corpus


def test_corpus_roundtrip(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'a.txt').write_text('alpha beta gamma\n' * 200)
    (src / 'b.txt').write_text('alpha beta gamma\n' * 150 + 'delta epsilon\n' * 50)
    (src / 'bin.dat').write_bytes((b'\x00\x01\x02\x03' * 128) + (b'hello world' * 32))

    manifest = compress_corpus(src, tmp_path / 'packed')
    restored = decompress_corpus(manifest, tmp_path / 'restored')

    assert (restored / 'a.txt').read_text() == (src / 'a.txt').read_text()
    assert (restored / 'b.txt').read_text() == (src / 'b.txt').read_text()
    assert (restored / 'bin.dat').read_bytes() == (src / 'bin.dat').read_bytes()


def test_corpus_store_summary_and_read(tmp_path: Path):
    src = tmp_path / 'src2'
    src.mkdir()
    (src / 'one.txt').write_text(('lorem ipsum\n' * 200) + ('dolor sit amet\n' * 50))
    (src / 'two.txt').write_text(('lorem ipsum\n' * 180) + ('amet\n' * 100))

    store = CorpusStore.from_source(src, tmp_path / 'packed2')
    summary = store.summary()

    assert summary['files'] == 2
    assert summary['original_bytes'] == (src / 'one.txt').stat().st_size + (src / 'two.txt').stat().st_size
    assert store.read_bytes('one.txt') == (src / 'one.txt').read_bytes()
    assert store.read_bytes('two.txt') == (src / 'two.txt').read_bytes()

    with store.open_materialized() as mat:
        assert (mat / 'one.txt').read_bytes() == (src / 'one.txt').read_bytes()
        assert (mat / 'two.txt').read_bytes() == (src / 'two.txt').read_bytes()
