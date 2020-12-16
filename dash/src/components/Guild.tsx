import samus from "assets/samus.jpg"
import NotFound from "components/NotFound"
import React from "react"
import { useSelector } from "react-redux"
import { useParams } from "react-router-dom"
import { guildSelector } from "state"

interface GuildParams {
  id: string
}

function GuildView(): React.ReactElement {
  const params = useParams<GuildParams>()
  const { id: guildId } = params
  const guild = useSelector(guildSelector(guildId))

  if (!guild) return <NotFound />

  return (
    <div className="main-content">
      <h1>{guild.name}</h1>
      <p>For now here&apos;s a picture of my dog, Samus.</p>
      <img alt="Samus" src={samus} />
    </div>
  )
}

export default GuildView
