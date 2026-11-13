# Changelog

## [1.2.2](https://github.com/udondan/switch-parental-controls/compare/v1.2.1...v1.2.2) (2026-11-09)


### Documentation

* add trademark disclaimer ([#100](https://github.com/udondan/switch-parental-controls/issues/100)) ([b2a51b9](https://github.com/udondan/switch-parental-controls/commit/b2a51b9f8662ec240c9d0379767cff576487be11))

## [1.2.1](https://github.com/udondan/switch-parental-controls/compare/v1.2.0...v1.2.1) (2026-11-01)


### Dependencies

* **deps:** update python docker tag to v3.15 ([#84](https://github.com/udondan/switch-parental-controls/issues/84)) ([4f3e621](https://github.com/udondan/switch-parental-controls/commit/4f3e621d54a3b6a34eeb9896ecf2d0264046a874))

## [1.2.0](https://github.com/udondan/switch-parental-controls/compare/v1.1.4...v1.2.0) (2026-11-01)


### Features

* publish a Docker image to Docker Hub ([#80](https://github.com/udondan/switch-parental-controls/issues/80)) ([712f0c1](https://github.com/udondan/switch-parental-controls/commit/712f0c12bc3c8b4fa47fa616558b32c3c123fa75))


### Bug Fixes

* don't crash on out-of-range timestamps ([#83](https://github.com/udondan/switch-parental-controls/issues/83)) ([6b3d5ad](https://github.com/udondan/switch-parental-controls/commit/6b3d5ad37422834017f067b38f7307338fb0886b))
* don't report known players without playtime as not found ([#76](https://github.com/udondan/switch-parental-controls/issues/76)) ([48a8779](https://github.com/udondan/switch-parental-controls/commit/48a8779d3b9cf64385dd08d1c46d1392d1bb7628))


### Documentation

* add light/dark banner to README ([#79](https://github.com/udondan/switch-parental-controls/issues/79)) ([a024b01](https://github.com/udondan/switch-parental-controls/commit/a024b01e40120adcefae71cc16472e3820f4bbdf))
* move README badges below the banner ([#81](https://github.com/udondan/switch-parental-controls/issues/81)) ([4fabf8e](https://github.com/udondan/switch-parental-controls/commit/4fabf8e4d07c4ef83e282fc5bed636721ba64c86))

## [1.1.4](https://github.com/udondan/switch-parental-controls/compare/v1.1.3...v1.1.4) (2026-10-24)

Only development dependencies were updated. Nothing changed for users.

## [1.1.3](https://github.com/udondan/switch-parental-controls/compare/v1.1.2...v1.1.3) (2026-10-15)

Only development dependencies were updated. Nothing changed for users.

## [1.1.2](https://github.com/udondan/switch-parental-controls/compare/v1.1.1...v1.1.2) (2026-09-29)


### Bug Fixes

* migrate to MCP Python SDK 2.x ([#42](https://github.com/udondan/switch-parental-controls/issues/42)) ([cb5b85e](https://github.com/udondan/switch-parental-controls/commit/cb5b85efaff3b0c6ef92976ae08bf9b7802c56cf))

## [1.1.1](https://github.com/udondan/switch-parental-controls/compare/v1.1.0...v1.1.1) (2026-05-31)


### Bug Fixes

* bump pynintendoparental to 2.4.0 ([#32](https://github.com/udondan/switch-parental-controls/issues/32)) ([d7884c9](https://github.com/udondan/switch-parental-controls/commit/d7884c9206f94d88dd90590d0d673e0140c22765))


### Documentation

* fix ToC anchor links on PyPI ([#30](https://github.com/udondan/switch-parental-controls/issues/30)) ([56558d6](https://github.com/udondan/switch-parental-controls/commit/56558d6c896e2b6d8eb8ec568bc5060f3e59f2f3))

## [1.1.0](https://github.com/udondan/switch-parental-controls/compare/v1.0.0...v1.1.0) (2026-05-29)


### Features

* add `--day` filter to `playtime` ([#28](https://github.com/udondan/switch-parental-controls/issues/28)) ([77e6be1](https://github.com/udondan/switch-parental-controls/commit/77e6be1f5f75cf9fac2af58c902bbf4742d72e46))
* add `--player` filter to `playtime` and `monthly-summary` ([#27](https://github.com/udondan/switch-parental-controls/issues/27)) ([164ae63](https://github.com/udondan/switch-parental-controls/commit/164ae63f2519d72fa135c6968f4d9bf874b3a38d))
* add `playtime` command for per-day playtime history ([#22](https://github.com/udondan/switch-parental-controls/issues/22)) ([f0e5156](https://github.com/udondan/switch-parental-controls/commit/f0e5156e2e742f98e0ac3dd8edcad43eefc6c2cc))
* cache historic monthly play data ([#25](https://github.com/udondan/switch-parental-controls/issues/25)) ([cae61be](https://github.com/udondan/switch-parental-controls/commit/cae61be4048a32781ffaf112c2d0dfdebf120ac9))


### Documentation

* add CLAUDE.md ([#26](https://github.com/udondan/switch-parental-controls/issues/26)) ([413ea21](https://github.com/udondan/switch-parental-controls/commit/413ea21d70ffcb35d022bfefaf66d8e08880ed05))

## [1.0.0](https://github.com/udondan/switch-parental-controls/compare/v0.5.0...v1.0.0) (2026-05-28)


### Features

* add switch-parental-controls agent skill ([#18](https://github.com/udondan/switch-parental-controls/issues/18)) ([4088dcd](https://github.com/udondan/switch-parental-controls/commit/4088dcd431a80d930b0f01fd59d4af88a4081deb))


### Miscellaneous Chores

* force release 1.0.0 ([#21](https://github.com/udondan/switch-parental-controls/issues/21)) ([109b659](https://github.com/udondan/switch-parental-controls/commit/109b659eadb572b41023fc3f5932dbca1d0f2871))

## [0.5.0](https://github.com/udondan/switch-parental-controls/compare/v0.4.0...v0.5.0) (2026-05-25)


### Features

* add --version flag to CLI ([#16](https://github.com/udondan/switch-parental-controls/issues/16)) ([b11a089](https://github.com/udondan/switch-parental-controls/commit/b11a08935290049561a3d5d7fb2ffbfd39a4e9fe))

## [0.4.0](https://github.com/udondan/switch-parental-controls/compare/v0.3.0...v0.4.0) (2026-05-25)


### ⚠ BREAKING CHANGES

* rename NINTENDO_ env vars to SWITCH_PARENTAL_CONTROLS_ ([#15](https://github.com/udondan/switch-parental-controls/issues/15))
* rename MCP tools from nintendo_ to switch_ prefix ([#14](https://github.com/udondan/switch-parental-controls/issues/14))

### Features

* rename MCP tools from nintendo_ to switch_ prefix ([#14](https://github.com/udondan/switch-parental-controls/issues/14)) ([353b44f](https://github.com/udondan/switch-parental-controls/commit/353b44f01f04d40e4fbb1a518d2740d3ac662958))


### Documentation

* rework README to lead with CLI and improve auth documentation ([#12](https://github.com/udondan/switch-parental-controls/issues/12)) ([304d9be](https://github.com/udondan/switch-parental-controls/commit/304d9be50f3469e4f65509c39f1666ce58c596f4))


### Code Refactoring

* rename NINTENDO_ env vars to SWITCH_PARENTAL_CONTROLS_ ([#15](https://github.com/udondan/switch-parental-controls/issues/15)) ([cf8de67](https://github.com/udondan/switch-parental-controls/commit/cf8de67f3847c5cea53561aa8dbcac20caad9d78))

## [0.3.0](https://github.com/udondan/switch-parental-controls/compare/v0.2.0...v0.3.0) (2026-05-25)


### Features

* add CLI with persistent auth and smart device resolution ([#10](https://github.com/udondan/switch-parental-controls/issues/10)) ([816b916](https://github.com/udondan/switch-parental-controls/commit/816b916fe774344abdc8af7342021fca7c8227c2))

## [0.2.0](https://github.com/udondan/switch-parental-controls/compare/v0.1.0...v0.2.0) (2026-05-24)


### Features

* add PyPI publish workflow ([#2](https://github.com/udondan/switch-parental-controls/issues/2)) ([4847934](https://github.com/udondan/switch-parental-controls/commit/4847934d5cabf591439d073c27b088fa3a188a2e))
* initial commit ([#1](https://github.com/udondan/switch-parental-controls/issues/1)) ([7a52e29](https://github.com/udondan/switch-parental-controls/commit/7a52e29e9c82b9946e5507eddec6df1efc958117))
