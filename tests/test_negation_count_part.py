#!/usr/bin/env python3
"""negation_count 的回归测试。

运行：
    python3 -m unittest discover -s tests -v

规则改动前先跑一遍，改动后再跑一遍；任何一条变红都说明极性或作用域行为被改坏了。
"""
import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("negation_count", SCRIPTS / "negation_count.py")
nc = importlib.util.module_from_spec(spec)
sys.modules["negation_count"] = nc
spec.loader.exec_module(nc)
