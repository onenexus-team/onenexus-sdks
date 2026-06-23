# Source this file from direnv or from an interactive shell:
#
#   source scripts/dev-env.sh

_onenexus_dev_env_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_onenexus_uv_version="${ONENEXUS_UV_VERSION:-0.11.21}"

_onenexus_abort() {
    printf 'onenexus dev-env: %s\n' "$1" >&2
    return 1 2>/dev/null || exit 1
}

_onenexus_prepend_path() {
    local _onenexus_path_entry="$1"
    local _onenexus_old_path=":$PATH:"

    _onenexus_old_path="${_onenexus_old_path//:$_onenexus_path_entry:/:}"
    _onenexus_old_path="${_onenexus_old_path#:}"
    _onenexus_old_path="${_onenexus_old_path%:}"
    PATH="$_onenexus_path_entry${_onenexus_old_path:+:$_onenexus_old_path}"
}

_onenexus_ensure_command() {
    command -v "$1" >/dev/null 2>&1 || _onenexus_abort "missing required command: $1"
}

_onenexus_node_version="${ONENEXUS_NODE_VERSION:-}"
if [[ -z "$_onenexus_node_version" && -f "$_onenexus_dev_env_root/.node-version" ]]; then
    IFS= read -r _onenexus_node_version < "$_onenexus_dev_env_root/.node-version"
fi
[[ -n "$_onenexus_node_version" ]] || _onenexus_abort "could not read Node.js version from .node-version"

_onenexus_pnpm_version="${ONENEXUS_PNPM_VERSION:-}"
if [[ -z "$_onenexus_pnpm_version" ]]; then
    _onenexus_pnpm_version="$(sed -n 's/^[[:space:]]*"packageManager"[[:space:]]*:[[:space:]]*"pnpm@\([^"]*\)".*/\1/p' "$_onenexus_dev_env_root/ts/package.json" | head -n 1)"
fi
[[ -n "$_onenexus_pnpm_version" ]] || _onenexus_abort "could not read pnpm version from ts/package.json"

_onenexus_dotnet_sdk_version="${ONENEXUS_DOTNET_SDK_VERSION:-}"
if [[ -z "$_onenexus_dotnet_sdk_version" ]]; then
    _onenexus_dotnet_sdk_version="$(sed -n 's/^[[:space:]]*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$_onenexus_dev_env_root/global.json" | head -n 1)"
fi
[[ -n "$_onenexus_dotnet_sdk_version" ]] || _onenexus_abort "could not read .NET SDK version from global.json"

_onenexus_get_node_platform() {
    local _onenexus_node_os
    local _onenexus_node_arch

    case "$(uname -s)" in
        Linux) _onenexus_node_os="linux" ;;
        Darwin) _onenexus_node_os="darwin" ;;
        *) _onenexus_abort "unsupported Node.js OS: $(uname -s)" || return 1 ;;
    esac

    case "$(uname -m)" in
        x86_64 | amd64) _onenexus_node_arch="x64" ;;
        aarch64 | arm64) _onenexus_node_arch="arm64" ;;
        *) _onenexus_abort "unsupported Node.js architecture: $(uname -m)" || return 1 ;;
    esac

    printf '%s-%s\n' "$_onenexus_node_os" "$_onenexus_node_arch"
}

_onenexus_node_platform="$(_onenexus_get_node_platform)" || return 1
_onenexus_node_dir="$_onenexus_dev_env_root/.tools/node-v$_onenexus_node_version-$_onenexus_node_platform"
_onenexus_node_bin_dir="$_onenexus_node_dir/bin"

case "$_onenexus_node_platform" in
    darwin-*)
        _onenexus_node_archive_ext="tar.gz"
        _onenexus_node_tar_flags="-xzf"
        ;;
    *)
        _onenexus_node_archive_ext="tar.xz"
        _onenexus_node_tar_flags="-xJf"
        ;;
esac

_onenexus_has_node() {
    [[ -x "$_onenexus_node_bin_dir/node" ]] || return 1
    [[ "$("$_onenexus_node_bin_dir/node" --version 2>/dev/null)" == "v$_onenexus_node_version" ]]
}

_onenexus_ensure_node() {
    _onenexus_has_node && return 0

    _onenexus_ensure_command curl || return 1
    _onenexus_ensure_command tar || return 1

    _onenexus_node_archive="$_onenexus_dev_env_root/.tools/node-v$_onenexus_node_version-$_onenexus_node_platform.$_onenexus_node_archive_ext"
    _onenexus_node_tmp_dir="$_onenexus_dev_env_root/.tools/node-v$_onenexus_node_version-$_onenexus_node_platform.tmp"
    mkdir -p "$_onenexus_dev_env_root/.tools" || return 1

    if [[ ! -f "$_onenexus_node_archive" ]]; then
        printf 'onenexus dev-env: downloading Node.js %s for %s\n' "$_onenexus_node_version" "$_onenexus_node_platform" >&2
        curl -fsSL "https://nodejs.org/dist/v$_onenexus_node_version/node-v$_onenexus_node_version-$_onenexus_node_platform.$_onenexus_node_archive_ext" \
            -o "$_onenexus_node_archive" || return 1
    fi

    printf 'onenexus dev-env: installing Node.js %s into %s\n' "$_onenexus_node_version" "$_onenexus_node_dir" >&2
    rm -rf "$_onenexus_node_tmp_dir" "$_onenexus_node_dir"
    mkdir -p "$_onenexus_node_tmp_dir" || return 1
    if ! tar "$_onenexus_node_tar_flags" "$_onenexus_node_archive" -C "$_onenexus_node_tmp_dir"; then
        rm -f "$_onenexus_node_archive"
        rm -rf "$_onenexus_node_tmp_dir"
        return 1
    fi
    mv "$_onenexus_node_tmp_dir/node-v$_onenexus_node_version-$_onenexus_node_platform" "$_onenexus_node_dir" || return 1
    rm -rf "$_onenexus_node_tmp_dir"
}

_onenexus_has_pnpm() {
    [[ -x "$_onenexus_node_bin_dir/pnpm" ]] || return 1
    [[ "$("$_onenexus_node_bin_dir/pnpm" --version 2>/dev/null)" == "$_onenexus_pnpm_version" ]]
}

_onenexus_ensure_pnpm() {
    _onenexus_has_pnpm && return 0

    if [[ -x "$_onenexus_node_bin_dir/corepack" ]]; then
        printf 'onenexus dev-env: activating pnpm %s with corepack\n' "$_onenexus_pnpm_version" >&2
        COREPACK_HOME="$COREPACK_HOME" "$_onenexus_node_bin_dir/corepack" enable --install-directory "$_onenexus_node_bin_dir" || return 1
        COREPACK_HOME="$COREPACK_HOME" "$_onenexus_node_bin_dir/corepack" prepare "pnpm@$_onenexus_pnpm_version" --activate || return 1
        return 0
    fi

    [[ -x "$_onenexus_node_bin_dir/npm" ]] || _onenexus_abort "local Node.js does not include npm" || return 1
    printf 'onenexus dev-env: installing pnpm %s with local npm\n' "$_onenexus_pnpm_version" >&2
    npm_config_prefix="$_onenexus_node_dir" \
        npm_config_cache="$npm_config_cache" \
        "$_onenexus_node_bin_dir/npm" install --global --no-audit --fund=false "pnpm@$_onenexus_pnpm_version"
}

_onenexus_has_dotnet_sdk() {
    [[ -x "$DOTNET_HOME/dotnet" ]] || return 1
    "$DOTNET_HOME/dotnet" --list-sdks 2>/dev/null \
        | awk -v wanted="$_onenexus_dotnet_sdk_version" '$1 == wanted { found = 1 } END { exit found ? 0 : 1 }'
}

_onenexus_ensure_dotnet() {
    _onenexus_has_dotnet_sdk && return 0

    _onenexus_ensure_command curl || return 1

    _onenexus_dotnet_installer="$_onenexus_dev_env_root/.tools/dotnet-install.sh"
    mkdir -p "$(dirname "$_onenexus_dotnet_installer")" "$DOTNET_HOME" || return 1

    if [[ ! -f "$_onenexus_dotnet_installer" ]]; then
        printf 'onenexus dev-env: downloading dotnet-install.sh\n' >&2
        curl -fsSL https://dot.net/v1/dotnet-install.sh -o "$_onenexus_dotnet_installer" || return 1
        chmod +x "$_onenexus_dotnet_installer" || return 1
    fi

    printf 'onenexus dev-env: installing .NET SDK %s into %s\n' "$_onenexus_dotnet_sdk_version" "$DOTNET_HOME" >&2
    "$_onenexus_dotnet_installer" \
        --version "$_onenexus_dotnet_sdk_version" \
        --install-dir "$DOTNET_HOME" \
        --no-path
}

_onenexus_ensure_uv() {
    _onenexus_uv_bin="$_onenexus_dev_env_root/.tools/uv/uv"
    _onenexus_installed_uv_version=""

    if [[ -x "$_onenexus_uv_bin" ]]; then
        _onenexus_installed_uv_version="$("$_onenexus_uv_bin" --version 2>/dev/null | awk '{ print $2 }')"
    fi

    [[ "$_onenexus_installed_uv_version" == "$_onenexus_uv_version" ]] && return 0

    _onenexus_ensure_command curl || return 1

    mkdir -p "$_onenexus_dev_env_root/.tools/uv" || return 1

    printf 'onenexus dev-env: installing uv %s into %s\n' "$_onenexus_uv_version" "$_onenexus_dev_env_root/.tools/uv" >&2
    curl -LsSf "https://astral.sh/uv/$_onenexus_uv_version/install.sh" \
        | env UV_INSTALL_DIR="$_onenexus_dev_env_root/.tools/uv" INSTALLER_NO_MODIFY_PATH=1 sh
}

export DOTNET_HOME="$_onenexus_dev_env_root/.dotnet"
export DOTNET_ROOT="$DOTNET_HOME"
export DOTNET_CLI_HOME="$_onenexus_dev_env_root/.dotnet-home"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export DOTNET_MULTILEVEL_LOOKUP=0
export DOTNET_NOLOGO=1
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
export NUGET_PACKAGES="$_onenexus_dev_env_root/.nuget/packages"

export UV_CACHE_DIR="$_onenexus_dev_env_root/.uv-cache"
export UV_PROJECT_ENVIRONMENT="$_onenexus_dev_env_root/python/.venv"

export NODE_HOME="$_onenexus_node_dir"
export COREPACK_HOME="$_onenexus_dev_env_root/.tools/corepack"
export npm_config_cache="$_onenexus_dev_env_root/.tools/npm-cache"
export npm_config_store_dir="$_onenexus_dev_env_root/.tools/pnpm-store"

mkdir -p "$DOTNET_HOME" "$DOTNET_CLI_HOME" "$NUGET_PACKAGES" "$UV_CACHE_DIR" "$COREPACK_HOME" "$npm_config_cache" "$npm_config_store_dir" || return 1

if [[ "${ONENEXUS_DEV_ENV_SKIP_INSTALL:-}" != "1" ]]; then
    _onenexus_ensure_dotnet || return 1
    _onenexus_ensure_uv || return 1
    _onenexus_ensure_node || return 1
    _onenexus_prepend_path "$_onenexus_node_bin_dir"
    export PATH
    _onenexus_ensure_pnpm || return 1
fi

_onenexus_prepend_path "$_onenexus_dev_env_root/python/.venv/bin"
_onenexus_prepend_path "$_onenexus_node_bin_dir"
_onenexus_prepend_path "$_onenexus_dev_env_root/.tools/uv"
_onenexus_prepend_path "$DOTNET_HOME"
export PATH

unset -f _onenexus_abort _onenexus_prepend_path _onenexus_ensure_command _onenexus_get_node_platform _onenexus_has_node _onenexus_ensure_node _onenexus_has_pnpm _onenexus_ensure_pnpm _onenexus_has_dotnet_sdk _onenexus_ensure_dotnet _onenexus_ensure_uv
unset _onenexus_dev_env_root _onenexus_dotnet_sdk_version _onenexus_uv_version _onenexus_node_version _onenexus_pnpm_version _onenexus_node_platform _onenexus_node_dir _onenexus_node_bin_dir _onenexus_node_archive_ext _onenexus_node_tar_flags _onenexus_node_archive _onenexus_node_tmp_dir _onenexus_dotnet_installer _onenexus_uv_bin _onenexus_installed_uv_version