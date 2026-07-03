{
  description = "Catodoro — a Django/HTMX pomodoro game where you care for a cat";

  inputs = {
    # Use the machine's registry nixpkgs (nixpkgs-unstable), which ships
    # prebuilt Python 3.14 packages in the binary cache. Pinning the older
    # nixos-25.11 rev forced source builds whose test deps (astor) break on
    # 3.14. Swap this for a specific `github:NixOS/nixpkgs/<rev>` to pin.
    nixpkgs.url = "flake:nixpkgs";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      lib = pkgs.lib;
      python = pkgs.python314;

      # Runtime Python environment. Uses nixpkgs' packaged deps (Django 5.2 LTS
      # here); the app only relies on standard Django APIs and runs on it.
      # These are taken as-is so they resolve to prebuilt binaries from the
      # nixpkgs cache (avoiding source builds of test-only deps like astor,
      # which fails on Python 3.14). Keep the flake input up to date so the
      # cache has them: `nix flake update`.
      pythonEnv = python.withPackages (ps: [
        ps.django
        ps."django-htmx"
        ps."django-widget-tweaks"
        ps.gunicorn
        ps.whitenoise
      ]);

      # Project source, minus dev/build cruft that shouldn't land in the store.
      src = lib.cleanSourceWith {
        src = ./.;
        filter = path: _type:
          let base = baseNameOf path; in
          !(lib.elem base [
            ".venv" ".git" ".direnv" "staticfiles" "result"
            "__pycache__" "db.sqlite3" "node_modules"
          ]);
      };

      # The app itself: source + admin static collected at build time.
      appSrc = pkgs.stdenv.mkDerivation {
        pname = "catodoro-app";
        version = "0.1.0";
        inherit src;
        nativeBuildInputs = [ pythonEnv ];
        dontConfigure = true;

        buildPhase = ''
          runHook preBuild
          export HOME=$TMPDIR
          export DJANGO_SETTINGS_MODULE=catodoro.settings
          export CATODORO_DEBUG=False
          export CATODORO_SECRET_KEY=build-time-only-not-secret
          python manage.py collectstatic --noinput
          runHook postBuild
        '';

        installPhase = ''
          runHook preInstall
          mkdir -p $out/share/catodoro
          cp -r catodoro core templates manage.py staticfiles $out/share/catodoro/
          runHook postInstall
        '';
      };

      appHome = "${appSrc}/share/catodoro";

      # Shared shell preamble for the wrappers. Both the server and the manage
      # wrapper resolve the SQLite DB to the same writable location, so
      # `catodoro-manage` operates on the same database the server serves.
      commonEnv = ''
        export DJANGO_SETTINGS_MODULE=catodoro.settings
        export PYTHONPATH=${appHome}''${PYTHONPATH:+:$PYTHONPATH}
        export CATODORO_STATIC_ROOT=''${CATODORO_STATIC_ROOT:-${appHome}/staticfiles}
        export CATODORO_STATE_DIR=''${CATODORO_STATE_DIR:-$PWD}
        export CATODORO_DB_PATH=''${CATODORO_DB_PATH:-$CATODORO_STATE_DIR/db.sqlite3}
      '';

      manageBin = pkgs.writeShellApplication {
        name = "catodoro-manage";
        runtimeInputs = [ pythonEnv ];
        text = ''
          ${commonEnv}
          exec python ${appHome}/manage.py "$@"
        '';
      };

      # migrate + serve with gunicorn (WhiteNoise serves static from the app).
      serverBin = pkgs.writeShellApplication {
        name = "catodoro-server";
        runtimeInputs = [ pythonEnv ];
        text = ''
          ${commonEnv}
          export CATODORO_DEBUG=''${CATODORO_DEBUG:-False}
          BIND=''${CATODORO_BIND:-0.0.0.0:8000}
          WORKERS=''${CATODORO_WORKERS:-3}

          mkdir -p "$CATODORO_STATE_DIR"
          echo "catodoro: migrating (db: $CATODORO_DB_PATH)"
          python ${appHome}/manage.py migrate --noinput
          echo "catodoro: serving on $BIND ($WORKERS workers)"
          exec gunicorn catodoro.wsgi:application \
            --chdir ${appHome} --bind "$BIND" --workers "$WORKERS"
        '';
      };

      catodoro = pkgs.symlinkJoin {
        name = "catodoro-0.1.0";
        paths = [ serverBin manageBin ];
      };
    in
    {
      packages.${system} = {
        default = catodoro;
        catodoro = catodoro;
        app = appSrc;
        pythonEnv = pythonEnv;
      };

      # `nix run` boots the server (migrations run automatically).
      # `nix run .#manage -- <cmd>` runs manage.py (e.g. createsuperuser).
      apps.${system} = {
        default = {
          type = "app";
          program = "${catodoro}/bin/catodoro-server";
        };
        manage = {
          type = "app";
          program = "${catodoro}/bin/catodoro-manage";
        };
      };

      # Deploy on a NixOS server: add this module and set services.catodoro.enable.
      nixosModules.default = { config, pkgs, lib, ... }:
        let cfg = config.services.catodoro;
        in {
          options.services.catodoro = {
            enable = lib.mkEnableOption "Catodoro pomodoro cat app";
            package = lib.mkOption {
              type = lib.types.package;
              default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
              description = "The catodoro package to run.";
            };
            bind = lib.mkOption {
              type = lib.types.str;
              default = "127.0.0.1:8000";
              description = "host:port gunicorn binds to.";
            };
            workers = lib.mkOption {
              type = lib.types.int;
              default = 3;
            };
            allowedHosts = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [ "localhost" "127.0.0.1" ];
              description = "Django ALLOWED_HOSTS.";
            };
            secretKeyFile = lib.mkOption {
              type = lib.types.nullOr lib.types.path;
              default = null;
              description = "Path to a file containing the Django SECRET_KEY.";
            };
          };

          config = lib.mkIf cfg.enable {
            systemd.services.catodoro = {
              description = "Catodoro";
              wantedBy = [ "multi-user.target" ];
              after = [ "network.target" ];
              environment = {
                CATODORO_DEBUG = "False";
                CATODORO_BIND = cfg.bind;
                CATODORO_WORKERS = toString cfg.workers;
                CATODORO_ALLOWED_HOSTS = lib.concatStringsSep "," cfg.allowedHosts;
                CATODORO_STATE_DIR = "/var/lib/catodoro";
                CATODORO_DB_PATH = "/var/lib/catodoro/db.sqlite3";
              };
              serviceConfig = {
                ExecStart = pkgs.writeShellScript "catodoro-start" ''
                  ${lib.optionalString (cfg.secretKeyFile != null) ''
                    CATODORO_SECRET_KEY="$(cat ${cfg.secretKeyFile})"
                    export CATODORO_SECRET_KEY
                  ''}
                  exec ${cfg.package}/bin/catodoro-server
                '';
                DynamicUser = true;
                StateDirectory = "catodoro";
                Restart = "on-failure";
                RestartSec = 2;
              };
            };

            # `sudo catodoro-manage <cmd>` on the server, e.g. `createsuperuser`.
            # Runs the command as a transient unit sharing the service's dynamic
            # user (User=catodoro) and its state directory, so it touches the
            # same database with the right permissions.
            environment.systemPackages = [
              (pkgs.writeShellScriptBin "catodoro-manage" ''
                exec systemd-run --pty --wait --collect \
                  --property=User=catodoro \
                  --property=DynamicUser=yes \
                  --property=StateDirectory=catodoro \
                  --setenv=CATODORO_STATE_DIR=/var/lib/catodoro \
                  ${cfg.package}/bin/catodoro-manage "$@"
              '')
            ];
          };
        };

      # `nix develop` — the original uv-based dev environment.
      devShells.${system}.default = pkgs.mkShell {
        name = "catodoro-dev-shell";
        buildInputs = [ python pkgs.uv pkgs.git pkgs.nodejs ];
        UV_PYTHON = "${python}/bin/python3";
        UV_PYTHON_DOWNLOADS = "never";
        ENVIRONMENT = "DEVELOPMENT";
        shellHook = ''
          uv sync
          source .venv/bin/activate
          echo "[v] Catodoro dev environment ready."
        '';
      };
    };
}
