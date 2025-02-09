cleanup() {
    # kill all processes whose parent is this process
    pkill -P $$
}

for sig in INT QUIT HUP TERM; do
  trap "
    cleanup
    trap - $sig EXIT
    kill -s $sig "'"$$"' "$sig"
done
trap cleanup EXIT

room=$(openssl rand -hex 12)
room=$room-timeout=1000-minPlayers=2-maxRounds=1000-defaultStack=5000-bigBlind=10-smallBlind=5
echo https://ff1a4817.my-app-22r.pages.dev/games/$room
python3.12 kellycriterion.py --host ws.turingpoker.com --port 80 --room $room --username "Queen" &
python3.12 kelyy.py --host ws.turingpoker.com --port 80 --room $room --username "King" 