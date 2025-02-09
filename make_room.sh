room=$(openssl rand -hex 12)
room=$room-timeout=1000-minPlayers=2-maxRounds=1000-defaultStack=5000-bigBlind=10-smallBlind=5
echo $room