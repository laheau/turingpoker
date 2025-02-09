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
echo $room
python3 kellycriterion.py --host ws.turingpoker.com --port 80 --room $room-timeout=1000-maxRounds=100-defaultStack=1000-bigBlind=10-smallBlind=5 --username "Always ALL IN" &
python3 kelyy.py --host ws.turingpoker.com --port 80 --room $room-timeout=1000-maxRounds=100-defaultStack=1000-bigBlind=10-smallBlind=5 --username "Always FOLD" 
echo