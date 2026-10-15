/* Forkashi desk copy. English first, Spanish second. Translate this object. */
window.FORKASHI_COPY = {
  en: {
    pauseBanner: "Game paused. Nothing is sent while you read.",
    chrome: {
      pauseKicker: "Paused",
      close: "Close",
      howtoLabel: "How it works",
    },
    splash: {
      kicker: "Forkashi",
      title: "Press start",
      body: "A practice desk for a $5 test payment. The money is not real.",
      start: "Press start",
      skip: "Skip",
    },
    steps: ["Receive", "Tap", "Confirm", "Settle"],
    badges: {
      loading: {
        kicker: "Desk",
        title: "Waiting for this desk…",
        detail: "The payment state shows up here.",
      },
      none: {
        kicker: "Waiting",
        title: "Nothing sent yet",
        detail: "No payment has been sent from this desk.",
        pending: "A plan is waiting. Nothing is sent until you type the exact phrase.",
      },
      sent: {
        kicker: "Sent",
        title: "Sent. Waiting for the other bill to import it",
        detail: "The other bill still needs to take the check in.",
      },
      accepted: {
        kicker: "Accepted",
        title: "Accepted — not yet settled on-chain",
        detail: "You have the check; the blockchain has not confirmed it yet.",
      },
      settled: {
        kicker: "Settled",
        title: "SETTLED ON-CHAIN. Final.",
        detail: "The test network has confirmed this payment.",
      },
      attention: {
        kicker: "Attention",
        title: "Needs attention",
        detail: "The desk could not tell if this payment is final.",
      },
    },
    cards: {
      check: {
        title: 'What is a "check"?',
        paragraphs: [
          'A check is a promise to pay that you hand to someone in person. It says "I will pay you $5."',
          "In this app, the check is a $5 USDT test payment.",
        ],
      },
      puck: {
        title: 'What is a "puck"?',
        paragraphs: [
          'A puck is the small gadget with a screen and a touch pad. People also call it the bill.',
          "It carries the payment from one person to the other over Bluetooth, tap to tap.",
          "It does not hold secret keys. The laptop dock does the wallet work.",
        ],
      },
      settlement: {
        title: 'What is "settlement"?',
        paragraphs: [
          "Settlement is the last step. The payment is written down on the Bitcoin test network, Mutinynet.",
          "Until that happens, the payment is not final.",
        ],
      },
      mutinynet: {
        title: 'What is Mutinynet / "test money"?',
        paragraphs: [
          "Mutinynet is a practice network. The money on it has no real value.",
          "You use it to learn the steps without risking real money.",
        ],
      },
      phrase: {
        title: "What does the typed confirmation phrase do?",
        paragraphs: [
          "It is a speed bump. You must type the exact words before money can be sent.",
          "That way a stray click cannot send the payment.",
        ],
      },
      accepted: {
        title: 'What are "accepted" and "settled"?',
        paragraphs: [
          "Accepted means you have the check. Settled means the blockchain has confirmed it. They are not the same.",
          "Accepted — not yet settled on-chain means you have the check, and the blockchain has not confirmed it yet.",
          "In this test version, the receiving dock still needs internet to import the check. Later versions aim to let you accept a check with no internet and settle afterward.",
          "Why isn't accepted the same as settled? Until the blockchain confirms the payment, the sender could in theory cancel it by spending the same coins somewhere else.",
        ],
      },
    },
    howto: {
      title: "How it works",
      intro: "Four steps. You can close this and open it again with the ? button.",
      steps: [
        {
          title: "1. Receiver picks Receive",
          text: "The person who will get the money presses Receive USDT on their dock.",
        },
        {
          title: "2. Tap the bills together",
          text: "Hold the two pucks so they touch. They pass the check over Bluetooth.",
        },
        {
          title: "3. Sender types the phrase",
          text: "The person who pays types the exact words. A wrong phrase sends nothing.",
        },
        {
          title: "4. Wait for settlement",
          text: "Accepted means the check arrived. Settled means the test network confirmed it.",
        },
      ],
    },
  },
  es: {
    pauseBanner: "Juego en pausa. No se envía nada mientras lees.",
    chrome: {
      pauseKicker: "Pausa",
      close: "Cerrar",
      howtoLabel: "Cómo funciona",
    },
    splash: {
      kicker: "Forkashi",
      title: "Pulsa inicio",
      body: "Un escritorio de práctica para un pago de prueba de $5. El dinero no es real.",
      start: "Pulsa inicio",
      skip: "Saltar",
    },
    steps: ["Recibir", "Tocar", "Confirmar", "Liquidar"],
    badges: {
      loading: {
        kicker: "Base",
        title: "Esperando a esta base…",
        detail: "El estado del pago aparece aquí.",
      },
      none: {
        kicker: "En espera",
        title: "Todavía no se envió nada",
        detail: "Desde esta base no se ha enviado ningún pago.",
        pending: "Hay un plan en espera. No se envía nada hasta que escribas la frase exacta.",
      },
      sent: {
        kicker: "Enviado",
        title: "Enviado. Falta que el otro billete lo importe",
        detail: "El otro billete todavía tiene que recibir el cheque.",
      },
      accepted: {
        kicker: "Aceptado",
        title: "Aceptado — aún no liquidado en la cadena",
        detail: "Tienes el cheque; la cadena de bloques todavía no lo confirmó.",
      },
      settled: {
        kicker: "Liquidado",
        title: "LIQUIDADO EN LA CADENA. Final.",
        detail: "La red de prueba confirmó este pago.",
      },
      attention: {
        kicker: "Atención",
        title: "Necesita atención",
        detail: "La base no pudo decir si este pago es final.",
      },
    },
    cards: {
      check: {
        title: "¿Qué es un cheque?",
        paragraphs: [
          "Un cheque es una promesa de pago que entregas en persona. Dice: «Te voy a pagar $5».",
          "En esta aplicación, el cheque es un pago de prueba de $5 USDT.",
        ],
      },
      puck: {
        title: "¿Qué es un puck?",
        paragraphs: [
          "Un puck es el aparato pequeño con pantalla y panel táctil. También se llama billete.",
          "Lleva el pago de una persona a la otra por Bluetooth, toque con toque.",
          "No guarda llaves secretas. La base del portátil hace el trabajo de la billetera.",
        ],
      },
      settlement: {
        title: "¿Qué es la liquidación?",
        paragraphs: [
          "La liquidación es el último paso. El pago queda anotado en la red de prueba de Bitcoin, Mutinynet.",
          "Hasta entonces, el pago no es final.",
        ],
      },
      mutinynet: {
        title: "¿Qué es Mutinynet y el dinero de prueba?",
        paragraphs: [
          "Mutinynet es una red de práctica. El dinero allí no tiene valor real.",
          "Sirve para aprender los pasos sin arriesgar dinero de verdad.",
        ],
      },
      phrase: {
        title: "¿Qué hace la frase de confirmación?",
        paragraphs: [
          "Es un tope de velocidad. Tienes que escribir las palabras exactas antes de que el dinero pueda salir.",
          "Así un clic sin querer no envía el pago.",
        ],
      },
      accepted: {
        title: "¿Qué diferencia hay entre aceptado y liquidado?",
        paragraphs: [
          "Aceptado significa que tienes el cheque. Liquidado significa que la cadena de bloques ya lo confirmó. No son lo mismo.",
          "«Aceptado — aún no liquidado en la cadena» quiere decir que tienes el cheque y que la cadena de bloques todavía no lo confirmó.",
          "En esta versión de prueba, la base que recibe todavía necesita internet para importar el cheque. Versiones posteriores buscan que puedas aceptar un cheque sin internet y liquidarlo después.",
          "¿Por qué aceptado no es lo mismo que liquidado? Hasta que la cadena de bloques confirme el pago, quien envía podría, en teoría, cancelarlo al gastar las mismas monedas en otro lugar.",
        ],
      },
    },
    howto: {
      title: "Cómo funciona",
      intro: "Cuatro pasos. Puedes cerrar esto y abrirlo otra vez con el botón ?.",
      steps: [
        {
          title: "1. Quien recibe elige Recibir",
          text: "La persona que va a recibir el dinero pulsa Recibir USDT en su base.",
        },
        {
          title: "2. Junta los billetes",
          text: "Acerca los dos pucks hasta que se toquen. Pasan el cheque por Bluetooth.",
        },
        {
          title: "3. Quien paga escribe la frase",
          text: "La persona que paga escribe las palabras exactas. Si la frase no coincide, no se envía nada.",
        },
        {
          title: "4. Espera la liquidación",
          text: "Aceptado significa que el cheque llegó. Liquidado significa que la red de prueba lo confirmó.",
        },
      ],
    },
  },
};
