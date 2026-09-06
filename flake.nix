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
        lib = pkgs.lib;
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

        # The CLI derivation sees only what the wheel needs. Edits under
        # plugins/ (the agent skill and the whitepaper) do not rebuild it.
        cliSrc = lib.fileset.toSource {
          root = ./.;
          fileset = lib.fileset.unions [
            ./pyproject.toml
            ./README.md
            ./LICENSE
            ./src
          ];
        };

        # The whitepaper ships inside the surf skill as its TeX and PDF
        # example. surf.tex is the source of truth; surf.pdf is committed so
        # an installed plugin carries it without a TeX toolchain.
        whitepaperSrc = ./plugins/surf/skills/surf/references;

        # Build-time only. Nothing here reaches packages.default.
        tex = pkgs.texliveSmall.withPackages (ps: with ps; [
          booktabs
          fancyvrb
          geometry
          hyperref
          lm
          microtype
          upquote
        ]);

        surf = pythonPkgs.buildPythonApplication {
          pname = "surf";
          version = "0.7.0";
          src = cliSrc;
          pyproject = true;

          build-system = with pythonPkgs; [
            hatchling
          ];

          dependencies = [ pypdf ];

          doCheck = false;
        };

        whitepaper = pkgs.stdenvNoCC.mkDerivation {
          name = "surf-whitepaper";
          src = whitepaperSrc;
          nativeBuildInputs = [ tex ];
          buildPhase = ''
            # Nix sets SOURCE_DATE_EPOCH; pdfTeX honors it only when forced,
            # which drops timestamps and the trailer ID from the PDF.
            export FORCE_SOURCE_DATE=1
            # Two passes: the first writes surf.out, the second reads it
            # back into the PDF outline that surf addresses.
            pdflatex -interaction=nonstopmode -halt-on-error surf.tex
            pdflatex -interaction=nonstopmode -halt-on-error surf.tex
          '';
          installPhase = ''
            install -Dm644 surf.pdf $out/surf.pdf
          '';
        };

        renderWhitepaper = pkgs.writeShellApplication {
          name = "render-whitepaper";
          runtimeInputs = [ pkgs.git pkgs.nix ];
          text = ''
            # Rebuild surf.pdf from surf.tex and copy it into the skill.
            # This is the only path by which the committed PDF changes.
            root="$(git rev-parse --show-toplevel)"
            out="$(nix build "$root#whitepaper" --no-link --print-out-paths)"
            install -m644 "$out/surf.pdf" "$root/plugins/surf/skills/surf/references/surf.pdf"
            echo "wrote plugins/surf/skills/surf/references/surf.pdf"
          '';
        };
      in {
        packages = {
          default = surf;
          inherit whitepaper;
        };

        apps.render-whitepaper = {
          type = "app";
          program = "${renderWhitepaper}/bin/render-whitepaper";
        };

        # surf is the comparator. The committed PDF must list the same tree
        # as a fresh render (no drift from surf.tex), and the TeX and PDF
        # fixtures must list the same tree as each other (one address works
        # on both). Comparing surf output rather than bytes keeps the check
        # green across TeX Live upgrades that perturb the PDF without
        # changing a single outline entry.
        checks.whitepaper = pkgs.runCommand "surf-whitepaper-check" {
          nativeBuildInputs = [ surf ];
        } ''
          committed=${whitepaperSrc}/surf.pdf
          fresh=${whitepaper}/surf.pdf
          tex=${whitepaperSrc}/surf.tex

          echo "committed PDF vs fresh render"
          diff <(surf --list "$committed") <(surf --list "$fresh")

          echo "TeX tree vs PDF tree"
          diff <(surf --list "$tex") <(surf --list "$committed")

          echo "every heading extracts from both"
          surf --list "$tex" | sed -e 's/^ *- //' | while read -r heading; do
            surf "$tex" "$heading" > /dev/null
            surf "$committed" "$heading" > /dev/null
          done

          touch $out
        '';

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
