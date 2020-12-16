import logo from "assets/logo.png"
import LoginButton from "components/LoginButton"
import React, { useEffect, useState } from "react"
import Button from "react-bootstrap/Button"
import { useSelector } from "react-redux"
import { Link, useHistory } from "react-router-dom"
import { discordUsernameSelector, loggedInSelector } from "state"
import "styles/Nav.css"

function Nav(): React.ReactElement {
  const [prevScrollPos, setPrevScrollPos] = useState(0)
  const [short, setShort] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const history = useHistory()
  const discordUsername = useSelector(discordUsernameSelector)
  const loggedIn = useSelector(loggedInSelector)

  const navbarClasses = () => {
    const classes = [
      "navbar",
      "navbar-expand-xl",
      "fixed-top",
      "navbar-custom",
      "top-nav-regular",
      "navbar-dark",
    ]
    if (expanded) classes.push("top-nav-expanded")
    return classes.join(" ")
  }

  const collapseClasses = () => {
    const classes = ["collapse", "navbar-collapse"]
    if (expanded) classes.push("show")
    return classes.join(" ")
  }

  const handleExpanderClick = () => setExpanded(!expanded)
  const goHome = () => history.push("/")

  useEffect(() => {
    const handleScroll = () => {
      const currentScrollPos = window.pageYOffset
      if (!short && currentScrollPos > prevScrollPos && currentScrollPos > 50) {
        setShort(true)
      } else if (
        short &&
        currentScrollPos < prevScrollPos &&
        currentScrollPos < 50
      ) {
        setShort(false)
      }
      setPrevScrollPos(currentScrollPos)
    }

    window.addEventListener("scroll", handleScroll)
    return () => window.removeEventListener("scroll", handleScroll)
  }, [prevScrollPos, short])

  return (
    <div className={`${navbarClasses()} ${short ? "top-nav-short" : ""}`}>
      <Button
        className={`navbar-brand ${loggedIn ? "visible" : "invisible"}`}
        variant="link"
        onClick={goHome}
      >
        {discordUsername}
      </Button>
      <button
        className="navbar-toggler"
        type="button"
        data-toggle="collapse"
        data-target="#main-navbar"
        aria-controls="main-navbar"
        aria-expanded="false"
        aria-label="Toggle navigation"
        onClick={handleExpanderClick}
      >
        <span className="navbar-toggler-icon" />
      </button>
      <div className={collapseClasses()} id="main-navbar">
        <ul className="navbar-nav ml-auto">
          <li key="login-button" className="nav-item">
            <LoginButton />
          </li>
        </ul>
      </div>
      <div className="avatar-container">
        <div className="avatar-img-border">
          <Link to="/">
            <img src={logo} className="avatar-img" alt="logo" />
          </Link>
        </div>
      </div>
    </div>
  )
}

export default Nav
