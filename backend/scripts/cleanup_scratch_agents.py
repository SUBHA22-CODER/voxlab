import sqlite3

con = sqlite3.connect("voxlab.db")
cur = con.cursor()

# Find IDs of scratch agents
cur.execute("SELECT id FROM agents WHERE name LIKE 'Audit %'")
scratch_ids = [row[0] for row in cur.fetchall()]

if scratch_ids:
    placeholders = ",".join("?" for _ in scratch_ids)
    cur.execute(f"SELECT id FROM darwin_runs WHERE agent_id IN ({placeholders})", scratch_ids)
    run_ids = [row[0] for row in cur.fetchall()]
    
    if run_ids:
        r_placeholders = ",".join("?" for _ in run_ids)
        cur.execute(f"DELETE FROM darwin_findings WHERE run_id IN ({r_placeholders})", run_ids)
        cur.execute(f"DELETE FROM darwin_generations WHERE run_id IN ({r_placeholders})", run_ids)
        cur.execute(f"DELETE FROM darwin_runs WHERE id IN ({r_placeholders})", run_ids)
    
    cur.execute(f"DELETE FROM agents WHERE id IN ({placeholders})", scratch_ids)
    con.commit()
    print(f"Removed {len(scratch_ids)} scratch agents and {len(run_ids)} scratch runs.")
else:
    print("No scratch agents found.")

# Verify remaining agents
cur.execute("SELECT id, user_id, name, endpoint FROM agents")
remaining = cur.fetchall()
print(f"Remaining active agents ({len(remaining)}):")
for r in remaining:
    print(f"  Agent {r[0]}: User {r[1]} - {r[2]} ({r[3]})")

