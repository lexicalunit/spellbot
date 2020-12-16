import games from "assets/games.png"
import queues from "assets/queues.png"
import usage from "assets/usage.png"
import React from "react"

function Welcome(): React.ReactElement {
  return (
    <div className="main-content">
      <h1 data-testid="welcome-title">SpellBot Dashboard</h1>
      <p>
        The SpellBot Dashboard allows you to view activity statistics and
        preform configuration management for the Discord guilds that you
        administer.
      </p>
      <h2>Server Activity</h2>
      <img className="rainbow" alt="Activity Statistics" src={games} />

      <h2>Queue Time Analysis</h2>
      <img className="rainbow" alt="Queue Time Statistics" src={queues} />

      <h2>Statistics Summaries</h2>
      <img className="rainbow" alt="Summary Statistics" src={usage} />
    </div>
  )
}

export default Welcome
