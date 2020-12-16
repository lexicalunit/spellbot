import React from "react"
import Loader from "react-spinners/PuffLoader"

function Throb(): React.ReactElement {
  return (
    <div className="loader">
      <Loader color="rgb(90, 62, 253)" size={200} />
    </div>
  )
}

export default Throb
