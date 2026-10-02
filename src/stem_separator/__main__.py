import sys

if "--runtime-self-test" in sys.argv:
    from stem_separator.engine import separation_self_test

    result = separation_self_test()
    raise SystemExit(0 if result["runtime_ready"] and result["separator_api"] else 1)

from stem_separator.ui import main

if __name__ == "__main__":
    raise SystemExit(main())
