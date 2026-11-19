"""Compatibility entry point; geometry work now lives in main_geom_builder.py."""
from main_geom_builder import find_section_a_sources, main

if __name__ == '__main__':
    raise SystemExit(main())
