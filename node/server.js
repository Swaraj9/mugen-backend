const express = require("express");
const cors = require("cors");
const fs = require("fs");

const app = express();

app.use(cors());
app.use(express.json());

app.get("/", (req, res) => {
  res.status(201).json({ message: "Connected to Backend!" });
});

app.post("/runmodel", (req, res) => {
  const { amount, duration } = req.body.genInfo;
  console.log(duration);

  const spawn = require("child_process").spawn;
  const process = spawn("python", [
    "../python/mugenPredict.py",
    parseInt(duration),
  ]);
  console.log("process started")

  process.stderr.on("data", (err) => {
    console.log(err.toString());
    res.status(400).json({ result: err.toString() });
    return;
  });

  process.stdout.on("data", (data) => {
    console.log(data.toString());
    filePath = __dirname + "/Result/" + data.toString() + ".midi";
    fs.readFile(filePath, (err, data) => {
      if (err) {
        console.error(err);
        res.status(500).send("Internal Server Error");
        return;
      }
      res.setHeader("Content-Type", "audio/midi");
      res.sendFile(filePath);
      return;
    });
  });
});

const port = 10000;
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
