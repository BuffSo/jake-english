#!/bin/sh
# Starts the Mac server at login and again whenever it dies, as a launchd user agent (ADR-0012).
#
#   server/scripts/autostart.sh install    write the agent and start it (replaces an older one)
#   server/scripts/autostart.sh stop       stop it until `start` or the next login (to test a worktree server)
#   server/scripts/autostart.sh start      start it again after `stop`
#   server/scripts/autostart.sh restart    run the new code after a merge
#   server/scripts/autostart.sh status     loaded or not, pid, last exit code
#   server/scripts/autostart.sh uninstall  stop it and remove the agent
#   server/scripts/autostart.sh plist      print the agent it would write
#
# It can be run from the original folder or any worktree: the agent always runs the original folder's
# server/ (the first line of `git worktree list`). The home folder path is filled in here, at install,
# so the agent file itself is never committed. When cards use which command:
# docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md
set -eu

LABEL=dev.jakeso.english.server
DOMAIN="gui/$(id -u)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/jake-english/server.log"
HERE=$(cd "$(dirname "$0")" && pwd)

die() {
  echo "autostart: $*" >&2
  exit 1
}

server_dir() {
  root=$(git -C "$HERE" worktree list --porcelain 2>/dev/null | sed -n '1s/^worktree //p')
  [ -n "$root" ] || die "$HERE is not in a git checkout"
  [ -f "$root/server/.env" ] || die "$root/server/.env is missing; copy server/.env.example and fill it in first"
  printf '%s/server' "$root"
}

find_tool() {
  command -v "$1" 2>/dev/null || die "$1 is not on PATH; the server needs it (server/README.md)"
}

xml() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

make_plist() {
  server=$(server_dir)
  uv=$(find_tool uv)
  ffmpeg=$(find_tool ffmpeg)
  whisper=$(find_tool whisper-server)
  # launchd gives agents only the system folders, where Homebrew's tools are not
  path=""
  for d in "$(dirname "$uv")" "$(dirname "$ffmpeg")" "$(dirname "$whisper")" /usr/bin /bin /usr/sbin /sbin; do
    case ":$path:" in
      *":$d:"*) ;;
      *) path="${path:+$path:}$d" ;;
    esac
  done
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LABEL</string>
	<key>ProgramArguments</key>
	<array>
		<string>$(xml "$uv")</string>
		<string>run</string>
		<string>python</string>
		<string>-m</string>
		<string>je_server</string>
	</array>
	<key>WorkingDirectory</key>
	<string>$(xml "$server")</string>
	<key>EnvironmentVariables</key>
	<dict>
		<key>PATH</key>
		<string>$(xml "$path")</string>
	</dict>
	<key>RunAtLoad</key>
	<true/>
	<key>KeepAlive</key>
	<true/>
	<key>ProcessType</key>
	<string>Interactive</string>
	<key>StandardOutPath</key>
	<string>$(xml "$LOG")</string>
	<key>StandardErrorPath</key>
	<string>$(xml "$LOG")</string>
</dict>
</plist>
EOF
}

loaded() {
  launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1
}

# bootout returns at once while the server is still shutting whisper-server and the voice worker down
# (launchctl print shows "state = SIGTERMed"); wait until launchd lets the job go, so a worktree server
# started next finds their ports free. launchd sends SIGKILL after 20 seconds (ExitTimeOut).
unload() {
  loaded || return 0
  launchctl bootout "$DOMAIN/$LABEL" || true
  i=0
  while loaded; do
    i=$((i + 1))
    [ "$i" -le 60 ] || die "$LABEL is still stopping after 30 seconds; see: server/scripts/autostart.sh status"
    sleep 0.5
  done
}

installed() {
  [ -f "$PLIST" ] || die "not installed; run: server/scripts/autostart.sh install"
}

case "${1:-}" in
  plist)
    make_plist
    ;;
  install)
    agent=$(make_plist)  # stops here, before anything is written, if a tool or server/.env is missing
    mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
    unload
    printf '%s\n' "$agent" >"$PLIST"
    plutil -lint -s "$PLIST"
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "installed and started $LABEL"
    ;;
  uninstall)
    unload
    rm -f "$PLIST"
    echo "stopped $LABEL and removed its agent file"
    ;;
  stop)
    unload
    echo "stopped $LABEL until 'start' or the next login"
    ;;
  start)
    installed
    if loaded; then echo "$LABEL is already running"; else launchctl bootstrap "$DOMAIN" "$PLIST" && echo "started $LABEL"; fi
    ;;
  restart)
    installed
    if loaded; then launchctl kickstart -k "$DOMAIN/$LABEL"; else launchctl bootstrap "$DOMAIN" "$PLIST"; fi
    echo "restarted $LABEL"
    ;;
  status)
    if [ ! -f "$PLIST" ]; then
      echo "not installed"
    elif loaded; then
      tab=$(printf '\t')
      launchctl print "$DOMAIN/$LABEL" | grep -E "^$tab(state|pid|runs|last exit code) = "
    else
      echo "installed but stopped (until 'start' or the next login)"
    fi
    ;;
  *)
    sed -n '2,10s/^# \{0,1\}//p' "$0" >&2
    exit 2
    ;;
esac
