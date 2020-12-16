import Throb from "components/Throb"
import React from "react"
import { useSelector } from "react-redux"
import { Redirect, useLocation } from "react-router-dom"
import {
  discordTokenSelector,
  discordUsernameSelector,
  setDiscordToken,
  useAppDispatch,
} from "state"

function Login(): React.ReactElement {
  const dispatch = useAppDispatch()
  const location = useLocation()
  const discordToken = useSelector(discordTokenSelector)
  const discordUsername = useSelector(discordUsernameSelector)

  if (!discordToken) {
    const params = new URLSearchParams(location.hash)
    const accessToken = params.get("access_token")
    if (accessToken) dispatch(setDiscordToken(accessToken))
  }

  if (discordUsername) {
    return <Redirect to="/" />
  }

  return (
    <div className="main-content">
      <Throb />
    </div>
  )
}

export default Login
