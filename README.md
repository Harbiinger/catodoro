# 🐱 Catodoro

A cozy productivity game: get things done, keep your cat happy.

Catodoro wraps a to-do list and a Pomodoro-style focus timer in a virtual-pet
loop. You create **quests** (deadline-driven tasks), and completing them earns
**coins** and cheers up your cat. Miss a deadline and the cat sulks — neglect it
long enough and it wanders off. Spend coins in the **shop** on food, toys, and
accessories to care for your companion, and unlock **achievements** along the way.

Built with Django 6, htmx, and Tailwind, packaged for reproducible deployment
with Nix.

## Gameplay

- **Quests** — tasks with a title, deadline, and difficulty (easy / medium /
  hard). Coin rewards and penalties scale with difficulty and how tight the
  deadline is: crunch-time tasks pay more but cost more if you fail them.
  Overdue active quests auto-fail on your next visit.
- **The cat** — has `happiness` and `satiety` (0–100) that decay in real time,
  so the game needs no background scheduler; state is recomputed lazily on each
  request. Completing quests raises happiness; failing them hurts it. Mood
  (happy → content → hungry → angry → away) is derived from those stats.
- **Shop & care** — spend coins on food (restores satiety), toys (boosts
  happiness), and accessories (cosmetic, equippable on the cat).
- **Achievements** — admin-configurable goals tracked against metrics (login
  streak, quests done/failed, cat stats, items bought) that unlock for bonus coins.
- **Admin dashboard** — a staff-only stats overview at `/staff/` (user counts,
  quest/cat/economy/achievement aggregates).

## Project layout

A Django project split into focused apps:

| App            | Responsibility                                                        |
|----------------|-----------------------------------------------------------------------|
| `core`         | Custom email-based `User`, the player's `Player` wallet, world sync    |
| `cats`         | The `Cat` model: mood, stat decay, artwork, and setup/onboarding       |
| `tasks`        | Quests: creation, Pomodoro progress, completion/failure, coin economy  |
| `shop`         | Shop catalogue (`ShopItem`), owned items, feed/play/equip actions      |
| `achievements` | Admin-configured `Achievement`s and per-user unlock records            |
| `adminpanel`   | Staff-only read-only stats dashboard                                   |
| `catodoro`     | Project settings, root URLconf, WSGI                                   |

`core/services.py::sync_world` is the heart of the game loop — called at the top
of each view to bring the cat and quests up to date with wall-clock time.

Users log in with an **email address** (there is no username).

## Getting started (development)

The dev environment uses [`uv`](https://github.com/astral-sh/uv). With Nix:

```sh
nix develop        # runs `uv sync` and activates .venv
```

Or manually with uv:

```sh
uv sync
source .venv/bin/activate
```

Then set up the database and run the server:

```sh
python manage.py migrate
python manage.py seed_shop          # populate the shop catalogue
python manage.py createsuperuser    # prompts for email + password
python manage.py runserver
```

The app is served at http://127.0.0.1:8000 and the SQLite database is created at
`./db.sqlite3`.

## Running with Nix

The `flake.nix` packages the app together with a production server (gunicorn +
WhiteNoise for static files, SQLite for storage) — no separate web server needed.

```sh
nix run                            # migrates, then serves on 0.0.0.0:8000
nix run .#manage -- createsuperuser  # run any manage.py command
nix build                          # -> result/bin/catodoro-server, result/bin/catodoro-manage
```

## Configuration

Configured via environment variables (sensible dev defaults out of the box):

| Variable                 | Default                          | Purpose                             |
|--------------------------|----------------------------------|-------------------------------------|
| `CATODORO_SECRET_KEY`    | insecure dev key                 | **Set this in production.**         |
| `CATODORO_DEBUG`         | `True` (`False` when served)     | Django debug mode.                  |
| `CATODORO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]`      | Comma-separated allowed hosts.      |
| `CATODORO_DB_PATH`       | `$CATODORO_STATE_DIR/db.sqlite3` | Explicit SQLite path.               |
| `CATODORO_STATE_DIR`     | `$PWD`                           | Where the SQLite DB lives.          |
| `CATODORO_BIND`          | `0.0.0.0:8000`                   | gunicorn bind address.              |
| `CATODORO_WORKERS`       | `3`                              | gunicorn worker count.              |

## Deployment

The flake exposes a hardened NixOS module (`DynamicUser`, `StateDirectory`) that
runs migrations on start and serves the app, persisting the database in
`/var/lib/catodoro/`. Add the flake to your host and enable it:

```nix
{
  inputs.catodoro.url = "github:youruser/catodoro";

  # inside your nixosSystem modules:
  imports = [ catodoro.nixosModules.default ];

  services.catodoro = {
    enable = true;
    bind = "127.0.0.1:8000";
    allowedHosts = [ "catodoro.example.com" ];
    secretKeyFile = "/run/secrets/catodoro-secret";
  };
}
```

Put nginx/caddy in front for TLS and proxy to `bind`. On the server, run
management commands (e.g. creating the first superuser) with the installed
wrapper, which shares the service's user and state directory:

```sh
sudo catodoro-manage createsuperuser
```

> **Note:** when adding a new Django app, add its directory to the `cp -r` list
> in `flake.nix`'s `installPhase` — the packaged app ships only the listed
> directories.

## Tech stack

- **Django 6** (Python 3.14) with a custom email-based user model
- **htmx** + **django-htmx** for dynamic interactions without a SPA
- **Tailwind CSS** (via CDN) for styling
- **SQLite** storage; **gunicorn** + **WhiteNoise** in production
- **uv** for dependency management, **Nix** for reproducible builds and deploy
