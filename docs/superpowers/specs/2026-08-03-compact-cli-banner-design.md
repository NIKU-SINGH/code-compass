# Compact CLI Default Output

## Goal

Make the default `compass` experience concise and useful by removing the oversized ASCII banner.

## Behavior

Running `compass` without a subcommand will show:

- A short product description.
- The command usage pattern.
- The available `index` and `serve` commands.
- Guidance for opening command-specific help.

The output will not include the large `CODE COMPASS` ASCII artwork. Existing command behavior and
Typer's `compass --help` output will remain unchanged.

## Implementation

The no-subcommand callback will stop calling the banner renderer and will continue calling the
existing concise command-help renderer. The unused banner renderer and its banner-only imports will
be removed from `display.py`.

## Testing

A CLI integration test will invoke `compass` without arguments and verify that:

- The command exits successfully.
- Concise product and command guidance remains visible.
- The distinctive ASCII-art block is absent.

The existing CLI test suite and package build will be run before opening the pull request.
