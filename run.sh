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
<<<<<<< HEAD
options="-maxRounds=1000-defaultStack=5000-bigBlind=10-smallBlind=5"
echo https://ff1a4817.my-app-22r.pages.dev/games/$room-$options
python3 kelyy.py --host ws.turingpoker.com --port 80 --room $room-$options --username "alwaysfold" > logs/always_fold.log &
python3 kellykiller.py --host ws.turingpoker.com --port 80 --room $room-$options --username "alwaysallin" 
=======
<<<<<<< HEAD
room=$room-timeout=1000-minPlayers=2-maxRounds=1000-defaultStack=5000-bigBlind=10-smallBlind=5
echo https://ff1a4817.my-app-22r.pages.dev/games/$room
python3.12 kellycriterion.py --host ws.turingpoker.com --port 80 --room $room --username "Queen" &
python3.12 kelyy.py --host ws.turingpoker.com --port 80 --room $room --username "King" 
=======
options="-maxRounds=100-defaultStack=1000-bigBlind=10-smallBlind=5"
echo https://ff1a4817.my-app-22r.pages.dev/games/$room-$options
python3 real.py --host ws.turingpoker.com --port 80 --room $room-$options --username "alwaysfold" > logs/always_fold.log &
python3 main.py --host ws.turingpoker.com --port 80 --room $room-$options --username "alwaysallin" 
>>>>>>> refs/remotes/origin/mcgill-tournament
>>>>>>> refs/remotes/origin/mcgill-tournament
