import React from "react"
import "styles/Footer.css"

function Footer(): React.ReactElement {
  return (
    <footer>
      <div className="container-md footer">
        <div className="row">
          <div className="col-xl-8 offset-xl-2 col-lg-10 offset-lg-1 text-center">
            Amy Troschinetz • 2020 •{" "}
            <a href="http://spellbot.io">SpellBot.io</a>
          </div>
        </div>
      </div>
    </footer>
  )
}

export default Footer
