## About pyapi-checker

Tool for checking for and acknowledging Python API breaking changes. Inspired by [gradle-revapi](https://github.com/revapi/gradle-revapi) and built with the [aexpy](https://github.com/StardustDL/aexpy) API explorer.

## Usage

Once you've installed `pyapi-checker` in an environment in your project you can interface with the `pyapi` CLI.

`pyapi analyze` is the command for checking for API breaks in your project which will produce output like this if you have 2 API breaks for example, and also exit with exit code 1:

```
Python API breaks found in my-lib:
AddRequiredParameter: Add PositionalOrKeyword parameter (functions.bin.parse.parse): new_param.
MoveParameter: Move parameter (functions.bin.parse.parse): handle_errors: 3 -> 4.
```

So you would want to include `pyapi analyze` in your CI process to require developers to acknowledge API breaks when creating PRs on a library.

### Accepting Breaks

You can accept a single break via:

```bash
pyapi acceptBreak "{break code}" "{justification why this is ok}"
```

Or accept all breaks via:

```bash
pyapi acceptAllBreaks "{justification why this is ok}"
```

Accepted breaks will populate in the `.palantir/pyapi.yml` file looking like this:

```yaml
acceptedBreaks:
  version:
    projectName:
    - code: 'break code'
      justification: justification
```

### Version overrides

Sometimes the previous release will have a successfully applied git tag but a failed publish build. In this case pyapi-checker will fail as it cannot resolve the previous API to compare against. To resolve this, you can set a version override that will use a different version instead of the last git tag. To do so, use the

```bash
pyapi versionOverride <last-published-version>
```

command to use the last correctly published version instead. This will create an entry in `.palantir/pyapi.yml` of the following format:

```yaml
versionOverrides:
  version: <last-published-version>
```

## Configuration

### Python Index

After identifying the last published version preceeding your current commit, pyapi-checker downloads the corresponding wheel for your package and version from a Python index. If you do not specify an index then pyapi-checker uses the following in order (if set):

1. `PIP_INDEX_URL`
2. `UV_DEFAULT_INDEX`
3. `https://pypi.org/simple`

To manually set an index you can set the following configuration:

```toml
[tool.pyapi-checker]
index = "<your-index-url>"
```

## Implementation

`pyapi-checker` uses [aexpy](https://github.com/StardustDL/aexpy) to power it's API breakage detection. You can check out the list of types of API breaks that `aexpy` detects [here](https://github.com/StardustDL/aexpy/blob/main/docs/change-spec/description.md).

_Note: `aexpy` does not consider any breaks to an __internal__ module, function, attribute, etc. a high priority breaking change and thus we will not flag these breaks to you._

## Developer Setup

This repo uses `hatchw` which is a wrapper around [Hatch](https://github.com/pypa/hatch) which automatically installs Python (versions 3.9-3.13) (via uv) and Hatch in a repo-specific venv such that this repo uses Hatch in an isolated manner.

`hatchw` essentially passes all args to Hatch and so with our scripts in the `pyproject.toml` file the workflows are intended to be the following:

1. Run tests: `./hatchw run test`
2. Check formatting/linting/type checking: `./hatchw run check-format`
3. Format/fix linting issues: `./hatchw run format`
4. Build package: `./hatchw run build`

If you want to disable any output produced by `hatchw` itself pass the `--hatchw-quiet` flag which is not propagated to Hatch.
