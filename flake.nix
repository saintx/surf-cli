{
  description = "surf - Extract markdown sections by heading";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in {
        packages.default = pkgs.python312Packages.buildPythonApplication {
          pname = "surf";
          version = "0.3.0";
          src = ./.;
          pyproject = true;

          build-system = with pkgs.python312Packages; [
            hatchling
          ];

          dependencies = [];

          doCheck = false;
        };

        devShells.default = pkgs.mkShell {
          nativeBuildInputs = [
            pkgs.python312
            pkgs.uv
          ];

          shellHook = ''
            # Dev group (pytest) is in default-groups — uv sync always installs it.
            if [[ ! -d .venv ]]; then
              echo "-> Creating venv and installing dependencies (incl. dev/pytest)..."
              uv venv
            fi
            uv sync
            source .venv/bin/activate
            export PS1="[surf] \$ "
            echo "-> surf dev shell: $(python -V); pytest=$(command -v pytest || echo missing)"
          '';
        };
      }
    );
}
