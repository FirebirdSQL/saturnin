# SPDX-FileCopyrightText: 2021-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/component/recipe.py
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
# pylint: disable=R0913

"""Saturnin recipes


"""

from __future__ import annotations
from typing import Hashable
from uuid import UUID
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from configparser import ConfigParser, ExtendedInterpolation
from firebird.base.config import Config, EnumOption, StrOption, UUIDOption, PathOption
from firebird.base.types import Distinct, Error
from firebird.base.collections import Registry
from saturnin.base.config import directory_scheme

class RecipeType(Enum):
    """Recipe type.
    """
    SERVICE = 'service'
    BUNDLE = 'bundle'

class RecipeExecutionMode(Enum):
    """Recipe execution mode.
    """
    NORMAL = 'normal'
    DAEMON = 'daemon'

class SaturninRecipe(Config):
    """Saturnin recipe descriptor - configuration section.
    """
    def __init__(self):
        super().__init__('saturnin.recipe')
        #: Recipe type - `.RecipeType` enum.
        self.recipe_type: EnumOption = \
            EnumOption('recipe_type', RecipeType, "Type of recipe", required=True)
        #: Recipe execution mode - `.RecipeExecutionMode` enum.
        self.execution_mode: EnumOption = \
            EnumOption('execution_mode', RecipeExecutionMode, "Execution mode",
                       default=RecipeExecutionMode.NORMAL)
        #: Recipe executor (container). If not provided, the default executor according to recipe type is used.
        self.executor: PathOption = PathOption('executor', "Recipe executor.")
        #: Application (if any)
        self.application: UUIDOption = \
            UUIDOption('application', "Application UID")
        #: Description
        self.description: StrOption = \
            StrOption('description', "Recipe description", default="Not provided")

@dataclass(eq=True, order=False, frozen=True)
class RecipeInfo(Distinct): # pylint: disable=R0903
    """Dataclass recipe information record stored in recipe registry.

    Arguments:
        name: Recipe name
        recipe_type: Recipe type
        execution_mode: Recipe execution mode
        executor: Recipe executor
        application: Application to be used
        description: Recipe description
        filename: Path to recipe file
    """
    #: Recipe name
    name: str
    #: Recipe type
    recipe_type: RecipeType
    #: Recipe execution mode
    execution_mode: RecipeExecutionMode
    #: Recipe executor
    executor: Path
    #: Application to be used
    application: UUID
    #: Recipe description
    description: str
    #: Path to recipe file
    filename: Path
    def get_key(self) -> Hashable:
        "Returns service UID"
        return self.name

class RecipeRegistry(Registry):
    """Saturnin recipe registry.

    Holds `RecipeInfo` instances.
    """
    def load_from(self, directory: Path, *, ignore_errors: bool=False) -> None:
        """Populate registry from descriptors of installed recipes.

        Arguments:
          directory: Directory with recipe files.
          ignore_errors: When True, errors are ignored, otherwise `.Error` is raised.
        """
        recipe_cfg: SaturninRecipe = SaturninRecipe()
        cfg_file: ConfigParser = ConfigParser(interpolation=ExtendedInterpolation())
        for filename in directory.glob('*.cfg'):
            try:
                cfg_file.clear()
                cfg_file.read(filename)
            except Exception as exc:
                if ignore_errors:
                    continue
                raise Error(f"Failed to parse recipe '{filename}'") from exc
            try:
                recipe_cfg.clear()
                recipe_cfg.load_config(cfg_file)
            except Exception as exc:
                if ignore_errors:
                    continue
                raise Error(f"Malformed recipe '{filename}'") from exc
            self.store(RecipeInfo(filename.with_suffix('').name,
                                  recipe_cfg.recipe_type.value,
                                  recipe_cfg.execution_mode.value,
                                  recipe_cfg.executor.value,
                                  recipe_cfg.application.value,
                                  recipe_cfg.description.value,
                                  filename))

#: Saturnin recipe registry
recipe_registry: RecipeRegistry = RecipeRegistry()
if directory_scheme.recipes.is_dir():
    recipe_registry.clear()
    recipe_registry.load_from(directory_scheme.recipes)
