#!/usr/bin/env python3
"""
Script de teste para validar conformidade com RFC SKIP
"""
import requests
import json
import sys

# Configurações do teste
BASE_URL = "http://localhost:8080"
REMOTE_SYSTEM_ID = "KP_QuIIN_Client"


def test_capabilities():
    """
    Testa o endpoint /capabilities conforme RFC SKIP Seção 4.1
    """
    print("🔍 Testando GET /capabilities...")

    try:
        response = requests.get(f"{BASE_URL}/capabilities")
        assert response.status_code == 200, f"Status code esperado: 200, obtido: {response.status_code}"

        data = response.json()

        # Verificar campos obrigatórios conforme RFC
        required_fields = ['entropy', 'key', 'algorithm',
                           'localSystemID', 'remoteSystemID']
        for field in required_fields:
            assert field in data, f"Campo obrigatório '{field}' não encontrado"

        # Verificar tipos
        assert isinstance(
            data['entropy'], bool), "Campo 'entropy' deve ser boolean"
        assert isinstance(data['key'], bool), "Campo 'key' deve ser boolean"
        assert isinstance(data['algorithm'],
                          str), "Campo 'algorithm' deve ser string"
        assert isinstance(data['localSystemID'],
                          str), "Campo 'localSystemID' deve ser string"
        assert isinstance(data['remoteSystemID'],
                          list), "Campo 'remoteSystemID' deve ser array"

        print("✅ GET /capabilities - PASSED")
        return True

    except Exception as e:
        print(f"❌ GET /capabilities - FAILED: {e}")
        return False


def test_get_new_key():
    """
    Testa o endpoint GET /key?remoteSystemID=<id>&size=<bits> conforme RFC SKIP Seção 4.2
    """
    print("🔍 Testando GET /key (nova chave)...")

    try:
        # Teste básico com remoteSystemID
        response = requests.get(
            f"{BASE_URL}/key?remoteSystemID={REMOTE_SYSTEM_ID}")
        assert response.status_code == 200, f"Status code esperado: 200, obtido: {response.status_code}"

        data = response.json()

        # Verificar campos obrigatórios
        assert 'keyId' in data, "Campo 'keyId' não encontrado"
        assert 'key' in data, "Campo 'key' não encontrado"

        # Verificar formatos
        assert isinstance(data['keyId'], str), "Campo 'keyId' deve ser string"
        assert isinstance(data['key'], str), "Campo 'key' deve ser string"
        assert len(
            data['keyId']) == 32, "keyId deve ter 32 caracteres (128 bits em hex)"
        assert len(
            data['key']) == 64, "key deve ter 64 caracteres (256 bits em hex)"

        # Teste com tamanho específico
        response2 = requests.get(
            f"{BASE_URL}/key?remoteSystemID={REMOTE_SYSTEM_ID}&size=128")
        assert response2.status_code == 200, "Falha ao gerar chave com tamanho específico"

        data2 = response2.json()
        assert len(
            data2['key']) == 32, "key de 128 bits deve ter 32 caracteres em hex"

        # Teste sem remoteSystemID (deve falhar)
        response3 = requests.get(f"{BASE_URL}/key")
        assert response3.status_code == 400, "Deve retornar 400 quando remoteSystemID não é fornecido"

        global test_key_id
        test_key_id = data['keyId']  # Salvar para próximo teste

        print("✅ GET /key (nova chave) - PASSED")
        return True

    except Exception as e:
        print(f"❌ GET /key (nova chave) - FAILED: {e}")
        return False


def test_get_key_by_id():
    """
    Testa o endpoint GET /key/{keyId}?remoteSystemID=<id> conforme RFC SKIP Seção 4.2
    """
    print("🔍 Testando GET /key/{keyId}...")

    try:
        # Primeiro gerar uma chave
        response = requests.get(
            f"{BASE_URL}/key?remoteSystemID={REMOTE_SYSTEM_ID}")
        assert response.status_code == 200, "Falha ao gerar chave para teste"
        key_data = response.json()
        key_id = key_data['keyId']

        # Agora recuperar a chave pelo ID
        response2 = requests.get(
            f"{BASE_URL}/key/{key_id}?remoteSystemID={REMOTE_SYSTEM_ID}")
        assert response2.status_code == 200, f"Falha ao recuperar chave por ID: {response2.status_code}"

        data = response2.json()
        assert 'keyId' in data, "Campo 'keyId' não encontrado"
        assert 'key' in data, "Campo 'key' não encontrado"
        assert data['keyId'] == key_id, "keyId retornado não confere"

        # Teste com keyId inválido
        response3 = requests.get(
            f"{BASE_URL}/key/invalid_key_id?remoteSystemID={REMOTE_SYSTEM_ID}")
        assert response3.status_code == 400, "Deve retornar 400 para keyId inválido"

        # Teste sem remoteSystemID
        response4 = requests.get(f"{BASE_URL}/key/{key_id}")
        assert response4.status_code == 400, "Deve retornar 400 quando remoteSystemID não é fornecido"

        print("✅ GET /key/{keyId} - PASSED")
        return True

    except Exception as e:
        print(f"❌ GET /key/{{keyId}} - FAILED: {e}")
        return False


def test_get_entropy():
    """
    Testa o endpoint GET /entropy?minentropy=<bits> conforme RFC SKIP Seção 4.3
    """
    print("🔍 Testando GET /entropy...")

    try:
        # Teste básico (padrão 256 bits)
        response = requests.get(f"{BASE_URL}/entropy")
        assert response.status_code == 200, f"Status code esperado: 200, obtido: {response.status_code}"

        data = response.json()

        # Verificar campos obrigatórios
        assert 'randomStr' in data, "Campo 'randomStr' não encontrado"
        assert 'minentropy' in data, "Campo 'minentropy' não encontrado"

        # Verificar tipos e valores
        assert isinstance(data['randomStr'],
                          str), "Campo 'randomStr' deve ser string"
        assert isinstance(data['minentropy'],
                          int), "Campo 'minentropy' deve ser integer"
        assert data['minentropy'] == 256, "minentropy padrão deve ser 256"
        assert len(
            data['randomStr']) == 64, "randomStr de 256 bits deve ter 64 caracteres em hex"

        # Teste com tamanho específico
        response2 = requests.get(f"{BASE_URL}/entropy?minentropy=128")
        assert response2.status_code == 200, "Falha ao gerar entropia com tamanho específico"

        data2 = response2.json()
        assert data2['minentropy'] == 128, "minentropy deve ser 128"
        assert len(
            data2['randomStr']) == 32, "randomStr de 128 bits deve ter 32 caracteres em hex"

        # Teste com parâmetro inválido
        response3 = requests.get(f"{BASE_URL}/entropy?minentropy=invalid")
        assert response3.status_code == 400, "Deve retornar 400 para parâmetro inválido"

        print("✅ GET /entropy - PASSED")
        return True

    except Exception as e:
        print(f"❌ GET /entropy - FAILED: {e}")
        return False


def test_error_handling():
    """
    Testa o tratamento de erros conforme RFC SKIP Tabela 3
    """
    print("🔍 Testando tratamento de erros...")

    try:
        # Teste 404 - endpoint não existente
        response = requests.get(f"{BASE_URL}/nonexistent")
        assert response.status_code == 404, f"Deve retornar 404 para endpoint inexistente"

        # Teste 405 - método não suportado
        response2 = requests.post(f"{BASE_URL}/capabilities")
        assert response2.status_code == 405, f"Deve retornar 405 para método POST"

        print("✅ Tratamento de erros - PASSED")
        return True

    except Exception as e:
        print(f"❌ Tratamento de erros - FAILED: {e}")
        return False


def main():
    """
    Executa todos os testes de conformidade RFC SKIP
    """
    print("🚀 Iniciando testes de conformidade RFC SKIP")
    print("=" * 50)

    tests = [
        test_capabilities,
        test_get_new_key,
        test_get_key_by_id,
        test_get_entropy,
        test_error_handling
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 50)
    print(f"📊 Resultado: {passed}/{total} testes passaram")

    if passed == total:
        print("🎉 Todos os testes passaram! Servidor está em conformidade com RFC SKIP.")
        return 0
    else:
        print("⚠️  Alguns testes falharam. Verifique a implementação.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Testes interrompidos pelo usuário")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("❌ Erro: Não foi possível conectar ao servidor SKIP")
        print("   Certifique-se de que o servidor esteja rodando em http://localhost:8080")
        sys.exit(1)
