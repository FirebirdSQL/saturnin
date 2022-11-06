#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/base/recipe.py
# DESCRIPTION:    Saturnin recipes
# CREATED:        11.3.2021
#
# The contents of this file are subject to the MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Copyright (c) 2021 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""saturnin - Saturnin recipes


"""

from __future__ import annotations
#from typing import List
from enum import Enum, auto
from firebird.base.config import Config, EnumOption

class RecipeType(Enum):
    """Recipe type.
    """
    SERVICE = auto()
    BUNDLE = auto()
    APPLICATION = auto()

class SaturninRecipe(Config):
    """Saturnin recipe.
    """
    def __init__(self):
        super().__init__('saturnin.recipe')
        #: Recipe type
        self.recipe_type: EnumOption = EnumOption('recipe_type', "Type of recipe",
                                                  required=True)
