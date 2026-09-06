{
  description = "surf - Extract markdown, TeX, or PDF sections by heading";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pythonPkgs = pkgs.python312Packages;
        pypdf = pythonPkgs.buildPythonPackage rec {
          pname = "pypdf";
          version = "6.17.0";
          pyproject = true;
          src = pkgs.fetchPypi {
            inherit pname version;
            hash = "sha256-CXrQ2Cl3jsW2Fa6qXG2ktsrEmS+P2AtW+YoajABlc7s=";
          };
          build-system = [ pythonPkgs.flit-core ];
          doCheck = false;
          pythonImportsCheck = [ "pypdf" ];
        };
      in {
        packages.default = pythonPkgs.buildPythonApplication {
          pname = "surf";
          version = "0.6.4";
          src = ./.;
          pyproject = true;

          build-system = with pythonPkgs; [
            hatchling
          ];

          dependencies = [ pypdf ];

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
