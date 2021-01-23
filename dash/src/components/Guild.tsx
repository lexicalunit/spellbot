import NotFound from "components/NotFound"
import React, { useEffect } from "react"
import { useSelector } from "react-redux"
import { useParams } from "react-router-dom"
import {
  backendGuild,
  discordTokenSelector,
  guildDisplaySelector,
  guildSelector,
  loggedInSelector,
  useAppDispatch,
} from "state"

interface GuildParams {
  id: string
}

function GuildView(): React.ReactElement {
  const dispatch = useAppDispatch()
  const params = useParams<GuildParams>()
  const { id: guildId } = params
  const guild = useSelector(guildSelector(guildId))
  const loggedIn = useSelector(loggedInSelector)
  const discordToken = useSelector(discordTokenSelector)
  const guildDisplay = useSelector(guildDisplaySelector)

  useEffect(() => {
    if (!discordToken || !loggedIn) return
    dispatch(backendGuild({ discordToken, guildId }))
  }, [discordToken, loggedIn, dispatch, guildId])

  if (!guild) return <NotFound />

  if (!guildDisplay)
    return (
      <div className="main-content">
        <h1>{guild.name}</h1>
        <p>This guild is not configured to use SpellBot yet.</p>
        {/*
        <p>For now here&apos;s a picture of my dog, Samus.</p>
        <img alt="Samus" src={samus} /> */}
      </div>
    )

  return (
    <div className="main-content">
      <h1>{guild.name}</h1>
      <ul>
        <li>serverPrefix: {guildDisplay.serverPrefix}</li>
        <li>expireTimeMinutes: {guildDisplay.expireTimeMinutes}</li>
        <li>privateLinks: {`${guildDisplay.privateLinks}`}</li>
        <li>showSpectateLink: {`${guildDisplay.showSpectateLink}`}</li>
        <li>motdVisibilty: {guildDisplay.motdVisibilty}</li>
        <li>powerEnabled: {`${guildDisplay.powerEnabled}`}</li>
        <li>tagsEnabled: {`${guildDisplay.tagsEnabled}`}</li>
        <li>voiceEnabled: {`${guildDisplay.voiceEnabled}`}</li>
        <li>serverMotd: {guildDisplay.serverMotd}</li>
        <li>gamesPlayed: {guildDisplay.gamesPlayed}</li>
      </ul>
    </div>
  )
}

export default GuildView
