Timer.instance().clear();

var filePath = "C:/Users/saved/PycharmProjects/FishBot/responses.txt";

var lastLineContent = "";

function getLastLine(filePath) {
    var file = new java.io.File(filePath);
    if (!file.exists()) {
        print("File does not exist: " + filePath);
        return "";
    }

    var reader = null;
    var line = null;
    var lastLine = "";

    try {
        var fileStream = new java.io.FileInputStream(file);
        reader = new java.io.BufferedReader(new java.io.InputStreamReader(fileStream, "UTF-8"));

        while ((line = reader.readLine()) != null) {
            lastLine = line;
        }
    } catch (e) {
        print("Error reading file: " + e.message);
    } finally {
        if (reader !== null) {
            reader.close();
        }
    }
    return lastLine;
}

function monitorFile() {
    try {
        var currentLastLine = getLastLine(filePath);

        if (currentLastLine !== lastLineContent && currentLastLine !== "") {
            Call.sendChatMessage(currentLastLine);
            lastLineContent = currentLastLine;
        }
    } catch (e) {
        print("Error: " + e.message);
    }
}

Timer.schedule(function() {
    monitorFile();
}, 0, 0.5);