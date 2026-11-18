"""Helpers that build invented PIDT workspaces for the tests of the workspace sources."""
import os
import zipfile
from dataclasses import dataclass


@dataclass
class DocBlock:
    """One DATABLOCK of an invented flash document.

    ``data`` makes the FLASHDATA embedded (DATA), ``datafile`` makes it external (DATAFILE); with neither
    the block has no FLASHDATA at all.
    """
    name: str
    flash_name: str | None = None
    data: bytes | None = None
    datafile: str | None = None
    block_type: str = 'CODE'
    start: str = '00001000'
    size: str = '16'
    method: str | None = None
    session: str | None = 'S1'
    part_number: str | None = 'PN-1'


def odx_flash_document(blocks: list[DocBlock], ecus: tuple[str, ...] = ('ecu-a',)) -> bytes:
    """An ODX flash document with one DATABLOCK, one FLASHDATA and one session entry per block."""
    datablocks, flashdatas, sessions, descs = [], [], {}, []
    for number, item in enumerate(blocks, start=1):
        ref = ''
        if item.data is not None or item.datafile is not None:
            body = ('<DATA>%s</DATA>' % item.data.hex() if item.data is not None
                    else '<DATAFILE LATEBOUND-DATAFILE="false">%s</DATAFILE>' % item.datafile)
            method = ('<ENCRYPT-COMPRESS-METHOD>%s</ENCRYPT-COMPRESS-METHOD>' % item.method
                      if item.method else '')
            flashdatas.append('<FLASHDATA ID="F%d"><SHORT-NAME>%s</SHORT-NAME>%s%s</FLASHDATA>'
                              % (number, item.flash_name or item.name, method, body))
            ref = '<FLASHDATA-REF ID-REF="F%d"/>' % number
        datablocks.append(
            '<DATABLOCK ID="B%d" TYPE="%s"><SHORT-NAME>%s</SHORT-NAME>%s<SEGMENTS><SEGMENT>'
            '<SOURCE-START-ADDRESS>%s</SOURCE-START-ADDRESS><UNCOMPRESSED-SIZE>%s</UNCOMPRESSED-SIZE>'
            '</SEGMENT></SEGMENTS></DATABLOCK>' % (number, item.block_type, item.name, ref, item.start,
                                                  item.size))
        if item.session:
            sessions.setdefault(item.session, []).append('B%d' % number)
            if item.part_number:
                descs.append('<SESSION-DESC><SHORT-NAME>d%d</SHORT-NAME><PARTNUMBER>%s</PARTNUMBER>'
                             '<SESSION-SNREF SHORT-NAME="%s"/></SESSION-DESC>'
                             % (number, item.part_number, item.session))
    session_xml = ''.join(
        '<SESSION><SHORT-NAME>%s</SHORT-NAME><DATABLOCK-REFS>%s</DATABLOCK-REFS></SESSION>'
        % (name, ''.join('<DATABLOCK-REF ID-REF="%s"/>' % ref for ref in refs))
        for name, refs in sessions.items())
    layers = ''.join('<LAYER-REF DOCREF="%s"/>' % ecu for ecu in ecus)
    return ('<?xml version="1.0" encoding="UTF-8"?><ODX><FLASH><ECU-MEMS><ECU-MEM><MEM>'
            '<SESSIONS>%s</SESSIONS><DATABLOCKS>%s</DATABLOCKS><FLASHDATAS>%s</FLASHDATAS></MEM></ECU-MEM>'
            '</ECU-MEMS><ECU-MEM-CONNECTORS><ECU-MEM-CONNECTOR><SESSION-DESCS>%s</SESSION-DESCS>'
            '<LAYER-REFS>%s</LAYER-REFS></ECU-MEM-CONNECTOR></ECU-MEM-CONNECTORS></FLASH></ODX>'
            % (session_xml, ''.join(datablocks), ''.join(flashdatas), ''.join(descs), layers)).encode()


def write_zip(path: str, entries: dict[str, bytes]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def write_file(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as handle:
        handle.write(data)


def flash_folder(workspace: str, platform: str) -> str:
    return os.path.join(workspace, platform, 'flash-data', 'flash-data')


def write_pdx(workspace: str, platform: str, name: str, blocks: list[DocBlock], payloads: dict[str, bytes] = None,
              document_entry: str = 'doc.odx', ecus: tuple[str, ...] = ('ecu-a',)) -> str:
    """A PDX package with index.xml, one flash document and the payload entries; returns its path."""
    entries = {'index.xml': b'<index/>', document_entry: odx_flash_document(blocks, ecus)}
    entries.update(payloads or {})
    path = os.path.join(flash_folder(workspace, platform), name)
    write_zip(path, entries)
    return path


def write_loose_odx(workspace: str, platform: str, name: str, blocks: list[DocBlock],
                    ecus: tuple[str, ...] = ('ecu-a',)) -> str:
    path = os.path.join(flash_folder(workspace, platform), name)
    write_file(path, odx_flash_document(blocks, ecus))
    return path


def sw_cnt_areas_xml(areas: list[tuple[str, bytes | None]]) -> bytes:
    """A SW-CNT container with an XML declaration and one DATENBEREICH per (name, data) pair.

    ``None`` as data gives an area whose container text is not valid Base64.
    """
    import base64
    items = []
    for name, data in areas:
        text = '!!not base64!!' if data is None else base64.b64encode(data).decode()
        items.append('<DATENBEREICH><DATEN-NAME>%s</DATEN-NAME><START-ADR>0000A000</START-ADR>'
                     '<GROESSE-DEKOMPRIMIERT>10</GROESSE-DEKOMPRIMIERT><DATEN>%s</DATEN></DATENBEREICH>'
                     % (name, text))
    return ('<?xml version="1.0" encoding="UTF-8"?><SW-CNT><DATENBEREICHE>%s</DATENBEREICHE></SW-CNT>'
            % ''.join(items)).encode()


def mcr_folder(workspace: str, platform: str) -> str:
    return os.path.join(workspace, platform, 'mcr-data')


def write_pcc(workspace: str, platform: str, relative: str, entries: dict[str, bytes]) -> str:
    """A PCC package below the platform's mcr-data folder; returns its path."""
    path = os.path.join(mcr_folder(workspace, platform), *relative.split('/'))
    write_zip(path, entries)
    return path
