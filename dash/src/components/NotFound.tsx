import snek from "assets/404.png"
import React from "react"
import "styles/NotFound.css"

function NotFound(): React.ReactElement {
  return (
    <div className="not_found main-content">
      <h1>404 Page Not Found</h1>
      <p>My apologiesssssss, but I could not find thisss page.</p>
      <img alt="Page Not Found" src={snek} />
    </div>
  )
}

export default NotFound
