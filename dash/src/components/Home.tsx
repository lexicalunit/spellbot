import NotFound from "components/NotFound"
import React from "react"
import { useSelector } from "react-redux"
import { Link } from "react-router-dom"
import { guildsSelector, loggedInSelector } from "state"
import "styles/Home.css"

function Home(): React.ReactElement {
  const loggedIn = useSelector(loggedInSelector)
  const guilds = useSelector(guildsSelector)

  const guildsEmptyContent = (
    <>
      <p>
        SpellBot Dashboard can only be used for Discord guilds where you are
        either the owner or have Administrator permissions. It does not seem
        that you have any guilds that meet these conditions.
      </p>
    </>
  )

  const guildsListContent = (
    <>
      <p>
        The SpellBot Dashboard can only be used for Discord guilds where you are
        either the owner or have Administrator permissions. Choose one of the
        following guilds to view its dashboard.
      </p>
      <ul className="list-type1">
        {guilds.map((guild) => {
          return (
            <li key={guild.id}>
              <Link to={`/guild/${guild.id}`}>{guild.name}</Link>
            </li>
          )
        })}
      </ul>
    </>
  )

  const content = () => {
    if (guilds?.length) return guildsListContent
    if (!loggedIn) return NotFound
    return guildsEmptyContent
  }

  return (
    <div className="main-content">
      <h1>Your Guilds</h1>
      {content()}
    </div>
  )
}

export default Home
