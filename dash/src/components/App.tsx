import Guild from "components/Guild"
import Home from "components/Home"
import Login from "components/Login"
import Nav from "components/Nav"
import NotFound from "components/NotFound"
import Welcome from "components/Welcome"
import React, { useEffect } from "react"
import { useSelector } from "react-redux"
import { Route } from "react-router-dom"
import { AnimatedSwitch } from "react-router-transition"
import {
  backendLogin,
  discordTokenSelector,
  loggedInSelector,
  useAppDispatch,
} from "state"
import "styles/App.css"

function App(): React.ReactElement {
  const dispatch = useAppDispatch()
  const loggedIn = useSelector(loggedInSelector)
  const discordToken = useSelector(discordTokenSelector)

  useEffect(() => {
    if (!discordToken || loggedIn) return
    dispatch(backendLogin({ discordToken }))
  }, [discordToken, loggedIn, dispatch])

  const routes = [<Route path="/login" component={Login} />]
  if (loggedIn) {
    routes.push(<Route path="/guild/:id" component={Guild} />)
    routes.push(<Route exact path="/" component={Home} />)
  } else {
    routes.push(<Route exact path="/" component={Welcome} />)
  }
  routes.push(<Route component={NotFound} />)

  return (
    <>
      <Nav />
      <div className="main">
        <AnimatedSwitch
          atEnter={{ opacity: 0 }}
          atLeave={{ opacity: 0 }}
          atActive={{ opacity: 1 }}
          className="switch-wrapper"
        >
          {routes}
        </AnimatedSwitch>
      </div>
    </>
  )
}

export default App
