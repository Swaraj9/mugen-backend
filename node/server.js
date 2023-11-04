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

  const spawn = require("child_process").spawn;
  const process = spawn("python", [
    "../python/mugenPredict.py",
    parseInt(duration),
  ]);

  process.stdout.on("data", (data) => {
    filePath = __dirname + "/Result/" + data.toString() + ".midi";
    console.log(filePath)
    fs.readFile(filePath, (err, data) => {
      if (err) {
        console.error(err);
        res.status(500).send("Internal Server Error");
        return;
      }
      console.log("File Read")
      res.setHeader("Content-Type", "audio/midi");
      res.sendFile(filePath);
      console.log("Response Sent")
      return;
    });
  });

  process.stderr.on("data", (err) => {
    console.log(err.toString());
    res.status(400).json({ result: err.toString() });
    return;
  });
});

const port = 10000;
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
