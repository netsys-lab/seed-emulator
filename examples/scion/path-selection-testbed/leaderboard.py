#!/usr/bin/env python3
"""
SuperTuxKart Leaderboard Server
Displays player statistics from stkservers.db in a beautiful web interface
"""

import sqlite3
import os
from flask import Flask, render_template_string, jsonify
from datetime import datetime
import json

app = Flask(__name__)

# Configuration
DB_PATH = 'stkservers.db'  # Path to your database file
REFRESH_INTERVAL = 5  # Seconds between auto-refresh

def get_db_connection():
    """Create a database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_leaderboard_data():
    """
    Fetch leaderboard data from the database
    Note: You may need to adjust the SQL queries based on your actual database schema
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First, let's try to understand the database structure
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Available tables:", [table['name'] for table in tables])
        
        # Try common table names for player stats
        # Adjust this query based on your actual database schema
        leaderboard_data = []
        
        try:
            # This is a common structure - adjust based on your actual schema
            cursor.execute("""
                SELECT 
                    player_name,
                    SUM(score) as total_score,
                    COUNT(*) as races_played,
                    MIN(time) as best_time,
                    AVG(time) as avg_time
                FROM (
                    SELECT * FROM player_stats
                    UNION ALL
                    SELECT * FROM race_results
                ) 
                GROUP BY player_name
                ORDER BY total_score DESC
                LIMIT 50
            """)
            leaderboard_data = cursor.fetchall()
        except sqlite3.Error:
            # If the above doesn't work, try a simpler query
            # You'll need to adjust this based on your actual table structure
            try:
                cursor.execute("""
                    SELECT DISTINCT player_name, score, time 
                    FROM players 
                    ORDER BY score DESC 
                    LIMIT 50
                """)
                leaderboard_data = cursor.fetchall()
            except:
                # Fallback - get table info to help debug
                for table in tables:
                    print(f"\nTable: {table['name']}")
                    cursor.execute(f"PRAGMA table_info({table['name']})")
                    columns = cursor.fetchall()
                    print("Columns:", [col['name'] for col in columns])
        
        conn.close()
        
        # Convert to list of dicts
        return [dict(row) for row in leaderboard_data]
        
    except Exception as e:
        print(f"Database error: {e}")
        # Return sample data if database is not available
        return [
            {"player_name": "Player1", "total_score": 1000, "races_played": 10, "best_time": 65.3, "avg_time": 72.1},
            {"player_name": "Player2", "total_score": 950, "races_played": 8, "best_time": 68.2, "avg_time": 75.5},
            {"player_name": "Player3", "total_score": 900, "races_played": 12, "best_time": 70.1, "avg_time": 78.3},
        ]

def format_time(seconds):
    """Format time in seconds to MM:SS.ms format"""
    if seconds is None:
        return "--:--"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes:02d}:{secs:05.2f}"

# HTML Template with SuperTuxKart styling
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SuperTuxKart Leaderboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Fredoka+One&family=Comfortaa:wght@400;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Comfortaa', cursive;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #7e8ba3 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
            color: #fff;
            overflow-x: hidden;
        }
        
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320"><path fill="%23ffffff10" d="M0,96L48,112C96,128,192,160,288,186.7C384,213,480,235,576,213.3C672,192,768,128,864,128C960,128,1056,192,1152,208C1248,224,1344,192,1392,176L1440,160L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z"></path></svg>') no-repeat bottom;
            background-size: cover;
            pointer-events: none;
            z-index: 0;
        }
        
        .container {
            max-width: 1200px;
            width: 100%;
            z-index: 1;
            position: relative;
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
            animation: slideDown 0.6s ease-out;
        }
        
        .header h1 {
            font-family: 'Fredoka One', cursive;
            font-size: 4rem;
            color: #fff;
            text-shadow: 3px 3px 6px rgba(0,0,0,0.3), 0 0 30px rgba(255,255,255,0.3);
            margin-bottom: 10px;
            letter-spacing: 2px;
        }
        
        .header .subtitle {
            font-size: 1.2rem;
            color: #ffd700;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .update-time {
            text-align: center;
            margin-bottom: 20px;
            font-size: 0.9rem;
            color: #b3d9ff;
            opacity: 0.8;
        }
        
        .leaderboard {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            overflow: hidden;
            animation: fadeIn 0.8s ease-out;
        }
        
        .leaderboard-header {
            background: linear-gradient(135deg, #ff6b6b 0%, #ff8e53 100%);
            color: white;
            padding: 20px;
            font-weight: 700;
            display: grid;
            grid-template-columns: 80px 2fr 1fr 1fr 1fr 1fr;
            gap: 15px;
            font-size: 1.1rem;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
        }
        
        .leaderboard-body {
            max-height: 600px;
            overflow-y: auto;
        }
        
        .leaderboard-row {
            display: grid;
            grid-template-columns: 80px 2fr 1fr 1fr 1fr 1fr;
            gap: 15px;
            padding: 15px 20px;
            align-items: center;
            transition: all 0.3s ease;
            color: #333;
            border-bottom: 1px solid #eee;
            position: relative;
            overflow: hidden;
        }
        
        .leaderboard-row:hover {
            background: #f0f7ff;
            transform: translateX(5px);
        }
        
        .leaderboard-row:nth-child(even) {
            background: #f9f9f9;
        }
        
        .position {
            font-family: 'Fredoka One', cursive;
            font-size: 1.5rem;
            text-align: center;
            width: 60px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: #e0e0e0;
            color: #666;
        }
        
        .position.gold {
            background: linear-gradient(135deg, #ffd700, #ffed4e);
            color: #fff;
            box-shadow: 0 4px 15px rgba(255, 215, 0, 0.4);
        }
        
        .position.silver {
            background: linear-gradient(135deg, #c0c0c0, #e8e8e8);
            color: #fff;
            box-shadow: 0 4px 15px rgba(192, 192, 192, 0.4);
        }
        
        .position.bronze {
            background: linear-gradient(135deg, #cd7f32, #e8a55d);
            color: #fff;
            box-shadow: 0 4px 15px rgba(205, 127, 50, 0.4);
        }
        
        .player-name {
            font-weight: 700;
            font-size: 1.1rem;
            color: #2c3e50;
        }
        
        .stat {
            text-align: center;
            font-weight: 600;
        }
        
        .stat-value {
            color: #3498db;
        }
        
        .time {
            color: #e74c3c;
        }
        
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: scale(0.95);
            }
            to {
                opacity: 1;
                transform: scale(1);
            }
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            font-size: 1.2rem;
            color: #666;
        }
        
        /* Scrollbar styling */
        .leaderboard-body::-webkit-scrollbar {
            width: 10px;
        }
        
        .leaderboard-body::-webkit-scrollbar-track {
            background: #f1f1f1;
        }
        
        .leaderboard-body::-webkit-scrollbar-thumb {
            background: #3498db;
            border-radius: 5px;
        }
        
        .leaderboard-body::-webkit-scrollbar-thumb:hover {
            background: #2980b9;
        }
        
        /* Responsive design */
        @media (max-width: 768px) {
            .header h1 {
                font-size: 2.5rem;
            }
            
            .leaderboard-header,
            .leaderboard-row {
                grid-template-columns: 60px 2fr 1fr 1fr;
            }
            
            .leaderboard-header > :nth-child(5),
            .leaderboard-header > :nth-child(6),
            .leaderboard-row > :nth-child(5),
            .leaderboard-row > :nth-child(6) {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏁 SuperTuxKart Leaderboard 🏁</h1>
            <p class="subtitle">Race to the Top!</p>
        </div>
        
        <div class="update-time" id="updateTime">
            Last updated: <span id="lastUpdate">--</span>
        </div>
        
        <div class="leaderboard">
            <div class="leaderboard-header">
                <div>Rank</div>
                <div>Player</div>
                <div>Score</div>
                <div>Races</div>
                <div>Best Time</div>
                <div>Avg Time</div>
            </div>
            <div class="leaderboard-body" id="leaderboardBody">
                <div class="loading">Loading leaderboard...</div>
            </div>
        </div>
    </div>
    
    <script>
        function formatTime(seconds) {
            if (!seconds) return '--:--';
            const minutes = Math.floor(seconds / 60);
            const secs = (seconds % 60).toFixed(2);
            return `${minutes.toString().padStart(2, '0')}:${secs.padStart(5, '0')}`;
        }
        
        async function updateLeaderboard() {
            try {
                const response = await fetch('/api/leaderboard');
                const data = await response.json();
                
                const leaderboardBody = document.getElementById('leaderboardBody');
                leaderboardBody.innerHTML = '';
                
                data.forEach((player, index) => {
                    const row = document.createElement('div');
                    row.className = 'leaderboard-row';
                    row.style.animationDelay = `${index * 0.05}s`;
                    row.style.animation = 'fadeIn 0.5s ease-out forwards';
                    
                    const position = index + 1;
                    let positionClass = 'position';
                    if (position === 1) positionClass += ' gold';
                    else if (position === 2) positionClass += ' silver';
                    else if (position === 3) positionClass += ' bronze';
                    
                    row.innerHTML = `
                        <div class="${positionClass}">${position}</div>
                        <div class="player-name">${player.player_name || 'Unknown'}</div>
                        <div class="stat stat-value">${player.total_score || 0}</div>
                        <div class="stat">${player.races_played || 0}</div>
                        <div class="stat time">${formatTime(player.best_time)}</div>
                        <div class="stat time">${formatTime(player.avg_time)}</div>
                    `;
                    
                    leaderboardBody.appendChild(row);
                });
                
                // Update timestamp
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
                
            } catch (error) {
                console.error('Error updating leaderboard:', error);
                document.getElementById('leaderboardBody').innerHTML = 
                    '<div class="loading">Error loading leaderboard. Please check the server.</div>';
            }
        }
        
        // Initial load
        updateLeaderboard();
        
        // Auto-refresh every 5 seconds
        setInterval(updateLeaderboard, {{ refresh_interval }} * 1000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Serve the main leaderboard page"""
    return render_template_string(HTML_TEMPLATE, refresh_interval=REFRESH_INTERVAL)

@app.route('/api/leaderboard')
def api_leaderboard():
    """API endpoint for leaderboard data"""
    data = get_leaderboard_data()
    return jsonify(data)

if __name__ == '__main__':
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"Warning: Database file '{DB_PATH}' not found!")
        print("Make sure to place the stkservers.db file in the same directory as this script.")
        print("Running with sample data...")
    
    print("Starting SuperTuxKart Leaderboard Server...")
    print(f"Open http://localhost:5000 in your browser to view the leaderboard")
    print(f"Auto-refresh interval: {REFRESH_INTERVAL} seconds")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)