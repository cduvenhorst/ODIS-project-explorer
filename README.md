# ODIS project explorer

Nefarious Motorsports forum thread: [http://nefariousmotorsports.com/forum/index.php?topic=23836.0](http://nefariousmotorsports.com/forum/index.php?topic=23836.0)

---

This Python project is meant to unpack (and make use of) the data stored in MCD Runtime Projects ([colloquially known as "*.db and .key files*"](http://nefariousmotorsports.com/forum/index.php?topic=10318.msg108305#msg108305)).

Normally, these files are used by the MCD Kernel which is then used by ODIS or iDEX or whatever.
Provided with every ODIS installation is an app `MCD-Kernel/VWMCDClient.exe` which can be used to mess around with the projects at a much lower level.

To use this data, one would normally use the libraries from `Include_Libs` and `MCD-Kernel` to write their own C++/Java app that parses the objects.
There are a few issues with this approach, though:
  1. You have to either figure out how to calculate the "secret MAC" to unlock the kernel for use, or crack the .dll.
  2. Almost every function call must be guarded, as exceptions are thrown when the requested element is not defined.
  3. Some database elements are not directly accessible using the provided API, or at least hard to reach.

With this tool, you can approach the databases from the lowest level possible.
I hope it is useful for the study of ODX, J2534, UDS and whatever else.

## A bit of info

> [!NOTE]
> No projects/databases will ever be provided!
> Please bring your own :)

The way these projects work, is that the pairs of .db and .key files represent "Pools" (and "PoolID" refers to the filename without extension).
Each pool contains Objects.

Any object is stored as a data stream, whose bytes will be read as flags/strings/numbers etc.
Every one is stored differently, so... a lot of time was poured into Ghidra and x64dbg.
You can probably appreciate the work it took by taking a look inside the `object_loaders` folder.

Under no circumstances do I guarantee that I am loading every object type correctly.
On the contrary, many fields were named as what I felt they represented.
Basically every class in the C++ library inherits from other classes and I have to admit I couldn't really wrap my head around it when decompiled.

## Getting started

For text translation, HSQLDB is needed, which can only be used through Java.
Therefore, JPype will need to be installed:
```python
pip install jpype1
```

JPype1 is only needed for translations (the optional translation database and language arguments) and for `dumpHSQLDB.py`; all other scripts work without it.

On macOS, `bin/pbl_macos.dylib` (universal arm64 + x86_64) is used automatically instead of `bin/pbl.dll`.
It is built from the PBL sources in the `third_party/pbl` submodule; to rebuild it:
```
git submodule update --init
python3 tools/build_pbl.py
```

To run the tests:
```
python3 -m unittest discover -s tests -t . -v
```

For usage info of each script, call them with argument '**-h**' (or just look at the source code).

The scripts which have the option of text translation (`dumpDTC` and `parseMWB`) will need a database.
  - Take a look in your ODIS data folder (somewhere around `C:/ProgramData`), there should be a `DIDB/db` folder.
  - It must contain a .data file with name `didb_Base-...`, where '...' is a language like 'en_US'.
  - So, provide the scripts with that folder's path and the language suffix.

If you do not provide such a database, for `dumpDTC` you will not have the "more detailed description",
and for `parseMWB` everything will use its default LONG-NAME from ODX.

## Strict reading

Loading is lenient by default: bytes left over after an object is parsed, and content that is recognised but not read, are reported on the console.
Passing `strict=True` to `ObjectLoader` (or to `DbObject.load_object`) turns both into `UnreadContentError` exceptions, which is useful for verifying that a loader covers its object layout completely.

## Inventory

`tools/inventory.py` reads every pool of one or more projects in strict mode and counts, per object type, how many objects decode cleanly (`ok`), fail (`failed`, including unread bytes) or have no loader (`unknown`). A pool that cannot be read (for example a `.key` file without its `.db` file) gets its `pool_error` set to the error text, and the run continues with the next pool. A project whose string files are missing or unreadable gets a top-level `project_error` instead (with no pools); it is also appended to its line in `summary.txt`, and the run continues with the next project. A missing or unloadable `--library`, or an output path that cannot be created, ends the run with exit code 2 before anything is written.

```
python3 tools/inventory.py --output DIR PROJECT [PROJECT ...]
```

For each project it writes `DIR/<installation>-<project>.json` (installation is the name of the folder above `Projects-V`, otherwise the parent folder's name) and a short `DIR/summary.txt`. Failures are grouped under `"<type> | <ExceptionClassName>: <first message line>"` in `errors`. The tool exits with 0 after a completed run, even if objects failed.

> [!WARNING]
> The output contains per-project counts of proprietary data. **Never commit inventory output.** The tool refuses (exit code 2) to write anywhere inside the git working tree it belongs to, before creating any file.

## Script info

The scripts that work on `.bv` pools (`dumpMWB`, `parseMWB`, `dumpCoding`, `dumpAdaptations`, `dumpFreezeFrames`, `dumpDTC` and `dumpECUVariantPatterns`) check per base variant whether it is UDS.
A base variant counts as UDS if a protocol layer in its parent layer chain has a `protocol_type` starting with `ISO_15765_3` or `ISO_14229`.
A project that contains the protocol pool `0.0.0@PR_UDSOnCAN.pr` counts every base variant as UDS.
Any other base variant prints `Not UDS` and is skipped.

Services (coding, adaptations, measurement values) and DTC DOPs are looked up including those inherited along the parent layers: the variant's own entries come first, then those of each parent layer in turn (including what that parent inherits itself), where a name that is already present is skipped, and NOT-INHERITED lists are respected.

Which services `dumpCoding`, `dumpMWB`, `dumpAdaptations` and `parseMWB` read is decided by name first and by layout second (all in `common_utils/table_entries.py`):
  - If the variant has the VW service (`DiagnServi_ReadDataByIdentMeasuValue` for MWBs, `DiagnServi_WriteDataByIdentCalibData` for adaptations), only that service is used.
    For VW the entries and their order are unchanged, but some cases that used to abort now produce output: a row without DOP reference gets the structure `{"#error": ...}`, a row with a default value is accepted, and the fallback that reads a row whose name has spaces where the key text has underscores now also applies to coding and adaptations.
    Coding additionally gets `flat_layout` and `VRC_<variant>.json` (see `dumpCoding`), and `parseMWB` now reports a missing row as `Failed to find table row for ...`.
    The selection is by layout, with no switch on the manufacturer: an ECU variant that lacks the VW measurement or adaptation service name but has 0x22 or 0x2E services in the layout below now gets an `MWB_<variant>.json` or `ADP_<variant>.c` file, where it used to get none.
  - Otherwise every service is used whose request starts with the service ID (0x22 for MWBs, 0x2E for adaptations) at BYTE-POSITION 0 and that has exactly one table key at BYTE-POSITION 1 and exactly one table structure at BYTE-POSITION 3, both at byte edge.
    For 0x22, the key and structure are those of the one positive response; a service with a different number of positive responses, and references to objects that are no services, are skipped.
    The Coding services (see below) are never adaptations.
  - Coding is only selected by name (the first of these names that the variant has): `DiagnServi_WriteDataByIdentVariaCodinTextu` first, then `CodingValue_Write` (`CODING_SERVICE_NAMES`).

A table is read in one of two ways:
  - **Whole table** (VW services, or a key without row reference): every row of the table is read; for a name key the key's COMPU-SCALEs give the DIDs (as before), for a decimal key the numbers the rows are stored under.
  - **Row reference** (the key parameter names one row of the table): one service gives one entry, the one for that row.

Two kinds of table keys are understood: names (a text table whose entries are the row names; the DID comes from the key's COMPU-SCALEs) and decimal (a plain number; the DID is the number the row is stored under in the table).
Any other key is an error.
A referenced row that is missing in the table (message names the row and the service), or whose name matches no or more than one COMPU-SCALE of a name key, aborts the variant with a `RuntimeError`.

Each entry has `did`, `long_name`, `long_name_id`, `description`, `byte_position`, `bit_position` and `structure`.
Entries that no VW service delivers also have `services`, the sorted names of all services that deliver that row (several services can deliver the same row); VW entries never have it.
VW entries come first, in their order; all other entries follow, sorted by DID and then by service name.
A row whose DOP could not be found is not an error: its `structure` is `{"#error": ...}` (this used to fail for a row without DOP reference).

### `dumpProject` / `dumpAllProjects`

These modules will dump every Object from every Pool (from every Project).
Be advised that dumping all projects will require a few tens of gigabytes and take a couple of hours.
I personally worked with a separate partition that I could format to quickly delete all files.

In the current state, all my projects get dumped without errors.
I tried projects from 2020 and 2022.
It's possible that older/newer projects will fail to dump for various reasons, most likely unhandled object types,
or unhandled fields in handled object types (which I hardcoded since they were the same in all projects).

> [!TIP]
> ```powershell
> python dumpProject.py "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "O:/Projects"
> ```
> ```powershell
> python dumpAllProjects.py "C:/ProgramData/OE/MCD-Projects-E/VWMCD" "O:/Projects"
> ```

Keys that are names, hash keys without a string (shown as `hash <n>`) and multi-part records are read too; inline flash data in a multi-part record is only dumped as its length.
A pool that is missing from `rt_index.xml` is reported with the line `Pool <PoolID> is not listed in rt_index.xml`, and its `.c` file contains the line `Not listed in rt_index.xml`.
`dumpAllProjects` continues after an error in one project and exits with code 1 if any project failed.

### `dumpECUVariantPatterns`

This script will dump "ECU-VARIANT matching patterns", necessary for the "variant identification" procedure (selecting the appropriate file for an ECU).
Each pattern has `odx_file_identifier`, `odx_file_version` and `subsystem_part_number` (`None` if the pattern does not use them; if a service is repeated, its last value is used) and `matching_parameters`, which lists every matching parameter of the pattern in database order, with `service`, `response_parameter` (the short name path if the parameter has one, else its name) and `expected_value`.
Repeated and unknown services are kept in `matching_parameters`.
An ECU variant with a KWP2000 pattern (`MB_Identification_Read`, `DCX_Identification_Read` or `ActiveDiagnosticInformation_Read`) prints `Not for UDS` and gets no file; the other variants of the base variant are still dumped (upstream stopped at the first such variant).

> [!TIP]
> ```powershell
> python dumpECUVariantPatterns.py basevariant "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "0.0.0@BV_DashBoardUDS.bv" "O:/Patterns"
> ```
> ```powershell
> python dumpECUVariantPatterns.py project "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "O:/Patterns"
> ```
> ```powershell
> python dumpECUVariantPatterns.py projects "C:/ProgramData/OE/MCD-Projects-E/VWMCD" "O:/Patterns"
> ```

### `dumpDTC`

This script will dump "DTC definitions".
It will only dump the objects necessary for DTCs (= diagnostic trouble codes) - service 0x19.

> [!TIP]
> ```powershell
> python dumpDTC.py basevariant "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "0.0.0@BV_DashBoardUDS.bv" "O:/DTCs" "C:/ProgramData/OE/DIDB/db" en_US
> ```
> ```powershell
> python dumpDTC.py project "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "O:/DTCs" "C:/ProgramData/OE/DIDB/db" en_US
> ```
> ```powershell
> python dumpDTC.py projects "C:/ProgramData/OE/MCD-Projects-E/VWMCD" "O:/DTCs" "C:/ProgramData/OE/DIDB/db" en_US
> ```

### `dumpFreezeFrames`

This script will dump "Freeze Frame definitions".
It will only dump the objects necessary for DTC extended data records - service 0x19, mode 0x06.
Besides the VW Freeze Frame multiplexer (`MUX_DTCExtenDataRecor`), the environment data descriptions of each variant are dumped, including those inherited along the parent layers (own ones first, NOT-INHERITED lists respected).
They are written after the multiplexer cases, one block per description, with `long_name`, `description`, `all_value_env_data` (the environment data valid for every DTC, or `None`), `env_data` (the environment data specific to some DTCs, each with `short_name`, `long_name`, `description`, `byte_length`, `parameters` and its `dtc_values`) and `dtc_env_data` (the `dtc` to `env_data` assignments).
A variant with neither a multiplexer nor an environment data description gets no file.

> [!TIP]
> ```powershell
> python dumpFreezeFrames.py basevariant "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "0.0.0@BV_DashBoardUDS.bv" "O:/FFs" "C:/ProgramData/OE/DIDB/db" en_US
> ```
> ```powershell
> python dumpFreezeFrames.py project "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "O:/FFs" "C:/ProgramData/OE/DIDB/db" en_US
> ```
> ```powershell
> python dumpFreezeFrames.py projects "C:/ProgramData/OE/MCD-Projects-E/VWMCD" "O:/FFs" "C:/ProgramData/OE/DIDB/db" en_US
> ```

### `dumpAdaptations`

This script will dump "Adaptation definitions".
It will only dump the objects necessary for Calibration Data Writing (= values you can change in the ECU) - service 0x2E.
Besides the VW service, every other 0x2E service with the adaptation layout is dumped (see above), one entry per row, with the `services` field.

> [!TIP]
> ```powershell
> python dumpAdaptations.py basevariant "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "0.0.0@BV_DashBoardUDS.bv" "O:/ADPs"
> ```
> ```powershell
> python dumpAdaptations.py project "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "O:/ADPs"
> ```
> ```powershell
> python dumpAdaptations.py projects "C:/ProgramData/OE/MCD-Projects-E/VWMCD" "O:/ADPs"
> ```

### `dumpCoding`

This script will dump "Coding definitions".
It will only dump the objects necessary for Variant Coding - service 0x2E, DID 0x0600.
Both service names in `dumpCoding.CODING_SERVICE_NAMES` (`DiagnServi_WriteDataByIdentVariaCodinTextu` and `CodingValue_Write`) are accepted.

Per ECU-VARIANT it writes `VRC_<variant>.c` (as before; every entry now also has a `flat_layout`) and `VRC_<variant>.json`, an array of `did`, `long_name`, `long_name_id`, `services` (not for VW) and `flat_layout`.
The entries are sorted by DID and then by the first of their sorted service names (VW entries keep the order of the table).
The flat layout is the coding as a list of fields, without the nesting of the structures:
  - The top-level keys are `byte_length`, `note` and `fields`.
  - `byte_length` is the length of the coding in bytes (from the structure, or computed from its fields, or `null` with a `note` if it is not fixed or the structure is not available).
  - Each field has `byte_position` (absolute: counted from the first byte after the DID, with the positions of the enclosing structures added up), `bit_position` and `bit_length` (the ODX bit position within that byte), `bit_mask` (the mask taken from the field's DOP, `null` if the DOP has none), `long_name`, `long_name_id`, `parameter_type`, `values` (for a text table, each with `lower_limit`, `upper_limit`, `text` and `text_id`), `default` (the default value, or the constant of a constant parameter) and `note`.
  - `note` explains what is missing: no BYTE-POSITION (the position is `null`; a parameter in the row itself without position starts at the beginning of the coding data), a parameter type that is not expected in a coding structure, or a DOP that is not available or not expanded.

If the output file `VRC_<variant>.c` already exists, the variant is skipped (`Already done, skipping`) without looking at the `.json` file; to get the `.json` files for an older output folder, dump with overwrite (`basevariant` always overwrites).

> [!TIP]
> ```powershell
> python dumpCoding.py basevariant "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "0.0.0@BV_DashBoardUDS.bv" "O:/VRCs"
> ```
> ```powershell
> python dumpCoding.py project "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "O:/VRCs"
> ```
> ```powershell
> python dumpCoding.py basevariant "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "0.0.0@BV_DashBoardUDS.bv" "O:/VRCs" EV_Example
> ```
> ```powershell
> python dumpCoding.py projects "C:/ProgramData/OE/MCD-Projects-E/VWMCD" "O:/VRCs"
> ```

With the optional last argument `basevariant` dumps only that ECU-VARIANT (or the BASE-VARIANT, by its own name).
Besides its coding entries, the file then also contains the coding table rows that the variant's other non-VW MWB and adaptation services address by row reference, so one file shows everything that is coded.
These related rows are only added when the coding service is not the VW service and uses a row reference: they are the rows of the same coding table that the variant's measurement and adaptation services address.
An unknown name prints `Available ECU-VARIANTs:` with the list, fails with a `RuntimeError` and writes nothing.

### `dumpFlash`

This script dumps the flash data of a project as binary files: data files referenced by the flash pools (or found in a `flash-data` folder), inline flash data stored in the pools, seed key programs (`.dll`/`.exe` files outside `flash-data` and `ConfigData_*` folders) and the blocks of `SW-CNT` flash containers.
Nothing is decrypted or decompressed; the only decoding is Base64 decoding of `SW-CNT` blocks.
Flash contents are never printed to the console.

Files are written below `<output>/flash/`, except the other project files (see below) and the `mcr` entries of workspace packages (see below):
- Files from the project keep their relative path: `flash/<project>/<relative path>`.
- Inline data is written to `flash/<project>/<pool ID>/<block short name>.bin`.
- Decoded `SW-CNT` blocks are written to `flash/<project>/<container path without extension>/<block name>.bin`.
- Identical content is written once per run; later occurrences only get a row in the overview that points to the first file.

Besides the flash data, the script copies the other files of each project unchanged to `<output>/<project>/<relative path>`, beside `flash/`: every file except pools (`.db`/`.key`), string files (`AStringData*`, `UStringData*`), SDG files (`SDG_*`), files in `ConfigData_*` and `flash-data` folders, Java (`.jar`/`.class`), `.dll`/`.exe`, ZIP archives and files without extension. In MCD projects these are ODX sources, vehicle information (`.odx-v`), topology XML, `index.xml`, `rt_index.xml`, `MCD3D_CURR_PROJECT.INI` and `DatabaseVersionInfo.txt`. They are not deduplicated, get no row in the overview and no hexdump, but count in the space check.

`flash/flash_overview.csv` lists every occurrence with the columns `origin_kind, origin, source, ecu, part_number, session, block, block_type, start_address, size, uncompressed_size, method, data_kind, written_file, duplicate, note`.
Addresses are `0x%08X`, `method` is `0x%02X`, sizes are decimal bytes, and `note` collects remarks and errors separated by `; `.

`--hexdump` additionally writes `<file>.hexdump.txt` next to every dumped file.

Before anything is written, the needed space (contents, hexdumps, overview and project files) is compared with the free space of the output drive.
If it does not fit, nothing is written, not even a folder, and the exit code is 1.
The output folder must not be inside the source folder, and none of the folders written for a project (`<output>/<project>`, `<output>/flash`, `<output>/mcr`) may contain or lie inside the project folder; otherwise the script stops immediately with exit code 1 (`Output folder must not overlap the source folder`).
Read errors do not stop the run; they are noted in the overview and reported on stderr, and the exit code is 1. Errors when copying project files are only reported on stderr and counted (exit code 1); the overview does not mention them.

Both commands accept a PIDT workspace folder as an optional third argument.
Each sub folder of the workspace that contains `flash-data/flash-data` or `mcr-data` is a vehicle platform.
For every platform, the ODX flash documents in `*.pdx` packages, loose `*.odx` files and `*.pcc` packages (any depth below `mcr-data`) are read in addition to the project data.
- `project` uses `<workspace>/mapping.properties` (lines `pidt-vehicle-platform.<folder>=<regular expression>`) to select the platforms whose expression matches the whole project name.
  Without that file the script stops with exit code 1; if no expression matches, the run continues without workspace data.
- `projects` reads every platform of the workspace.
- `*.pdx` packages and loose `*.odx` files are read only directly in `<platform>/flash-data/flash-data/`.
- Flash data of a `.pdx` package is written to `flash/workspace/<package>/...`, that of a loose `.odx` file to `flash/workspace/<file without extension>/<FLASHDATA>.bin`, and the data set downloads of a `.pcc` package to `flash/workspace/<package>/<entry>/...`.
- The other entries of `.pcc` packages are copied unchanged to `<output>/mcr/<package>/...`, beside `flash/`.
- The `origin_kind` column is `workspace` or `pcc`, and `origin` is the platform folder.
- A full workspace needs on the order of 10 GB after deduplication.
- The workspace must be a folder, and the output folder must not be inside it.

> [!TIP]
> ```powershell
> python dumpFlash.py project "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "O:/Flash" --hexdump
> ```
> ```powershell
> python dumpFlash.py projects "C:/ProgramData/OE/MCD-Projects-E/VWMCD" "O:/Flash"
> ```
> ```powershell
> python dumpFlash.py projects "C:/ProgramData/OE/MCD-Projects-E/VWMCD" "O:/Flash" "D:/PIDT/workspace"
> ```

### `dumpMWB`

This script will dump "MWB definitions".
It will only dump the objects necessary for MWBs (= Messwertblöcke - Measuring blocks) - service 0x22.
Besides the VW service, every other 0x22 service with the measurement layout is dumped (see above), one entry per row, with the `services` field.

This is by far the most important and non-standardized part of UDS diagnostics, one of the main purposes of this project.

> [!TIP]
> ```powershell
> python dumpMWB.py basevariant "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "0.0.0@BV_DashBoardUDS.bv" "O:/MWBs"
> ```
> ```powershell
> python dumpMWB.py project "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "O:/MWBs"
> ```
> ```powershell
> python dumpMWB.py projects "C:/ProgramData/OE/MCD-Projects-E/VWMCD" "O:/MWBs"
> ```

### `parseMWB`

This script will take a UDS service 0x22 response and parse it similarly to the MCD Kernel.
It probably took the most amount of work, apart from the object loaders.

> [!TIP]
> ```powershell
> python parseMWB.py "C:/ProgramData/OE/MCD-Projects-E/VWMCD/AU21X" "0.0.0@BV_EnginContrModul1UDS.bv" "EV_ECM25TFS0118U0907404C_001" 0xF40C C0E4 "C:/ProgramData/OE/DIDB/db" en_US
> ```

A DID can be defined by several services; every entry of the DID is used to parse the response, and each is preceded by a `Services:` line (not for VW).
The script reads all entries of the ECU-VARIANT before it looks for the DID, so one bad table row (for example a missing row or an unexpected key) aborts it for the whole variant, even if the requested DID is fine.
A DID whose structure is not available (row without DOP) stops with `MWB structure not available`.

A few more examples are provided in `docs/mwb_examples.txt`.

### `dumpHSQLDB`

This script will dump the contents of all tables of an HSQLDB database.
The username and password are hardcoded, but I don't expect them to ever change.
If you encounter problems, check out the [following chapter](#hsqldb).

> [!TIP]
> ```powershell
> python dumpHSQLDB.py "C:/ProgramData/OE/DIDB/db" "didb_Base-en_US" "O:\HSQLDB"
> ```

## HSQLDB

The included `bin/hsqldb.jar` is an unmodified release from SourceForge, version 1.8.0.

If you encounter issues like "user does not exist" when providing a translation database,
you can rename `hsqldb.jar` to something else and rename `hsqldb_mod.jar` to `hsqldb.jar`.
That one has been modified to automatically dump all users and passwords of a database at startup.

> [!NOTE]
> The "user does not exist" error may also be shown if the database was somehow loaded incorrectly.
> Please ensure you provided the correct path.

The modified .jar will write something like this to the standard output:
```
Name: PUBLIC, password: null
Name: _SYSTEM, password: null
Name: SA, password: ENMGZIRN
Name: VAUDASISTSUPER, password: ENMGZIRN
```

As a side effect, this will always be printed when HSQLDB is used from one of the scripts that need it.

> [!TIP]
> If you wish to start a server from a database (for your own experiments), run this from inside the `bin` folder:
> ```powershell
> java -cp hsqldb.jar org.hsqldb.Server -database.0 file:"C:/ProgramData/OE/DIDB/db/didb_Base-en_US" -dbname.0 testdb
> ```
> You will connect to it using the URL `jdbc:hsqldb:hsql://localhost/testdb`.

## Contributing

If anyone else is dedicated/bored enough, they are very welcome to contribute to this project, even just submitting an issue.

If you want to add functionality (like dumping other important stuff), you are free to take a look how things are dumped currently,
like MWBs or DTCs, then use `dumpProject` and search around with a text editor for object names, fields and such.

## Extra info

In `docs/MCD-2D.md` you can find the documentation used for the validation of data, nicely formatted.

The included `bin/pbl.dll` is simply compiled from the PBL library by Mission-Base.
It is necessary for accessing the .key files.

---

No AI was harmed in the making of this waste of resources. Just a bit of help for the `LongNameTranslation` module. I couldn't be arsed to figure out Java and SQL integration myself.
