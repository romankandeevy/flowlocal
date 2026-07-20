// Пояснение под карточкой.
import QtQuick

Text {
    width: parent ? parent.width : 0
    wrapMode: Text.WordWrap
    font.family: T.sans
    font.pixelSize: T.tSm
    color: T.textMuted
    lineHeight: 1.3
}
