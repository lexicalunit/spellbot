import React from "react"
import Button from "react-bootstrap/Button"
import { useSelector } from "react-redux"
import { useHistory } from "react-router-dom"
import {
  backendLogout,
  clearState,
  discordTokenSelector,
  loggedInSelector,
  useAppDispatch,
} from "state"

const AUTH_BASE_ENDPOINT = "https://discord.com/oauth2/authorize"
const AUTH_PARAMS = new URLSearchParams({
  client_id: process.env.REACT_APP_CLIENT_ID || "",
  redirect_uri: process.env.REACT_APP_REDIRECT_URI || "",
  response_type: "token",
  scope: ["identify", "guilds"].join(" "),
})
const AUTH_URI = `${AUTH_BASE_ENDPOINT}?${AUTH_PARAMS}`

function LoginButton(): React.ReactElement {
  const history = useHistory()
  const dispatch = useAppDispatch()
  const loggedIn = useSelector(loggedInSelector)
  const discordToken = useSelector(discordTokenSelector)

  const login = () => window.location.assign(AUTH_URI)
  const logout = () => {
    if (discordToken) dispatch(backendLogout({ discordToken }))
    dispatch(clearState())
    history.push("/")
  }
  const click = () => (loggedIn ? logout() : login())
  const label = loggedIn ? "Logout" : "Login"

  return (
    <Button className="nav-link" variant="link" onClick={click}>
      {label}
    </Button>
  )
}

export default LoginButton
